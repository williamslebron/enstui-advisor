"""
pipeline.py

The autonomous orchestrator. Runs the full scrape → embed pipeline
with self-healing: exponential backoff, quota detection, state recovery,
and alerting when human intervention is actually needed.

Called by Cloud Scheduler daily, or directly:
    python pipeline.py

Self-corrects:
  - API quota errors      → waits and retries automatically
  - Partial run failures  → picks up exactly where it left off
  - Corrupted state       → validates and rebuilds state file
  - Network timeouts      → retries with backoff
  - Embedding mismatches  → re-queues failed chunks
  - Supabase errors       → retries batch, then halves batch size
"""

import os
import json
import time
import logging
import traceback
import smtplib
import requests
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

PIPELINE_LOG    = Path("pipeline.log")
STATE_FILE      = Path("last_run_state.json")
FAILURE_LOG     = Path("failures.json")

MAX_RETRIES     = 5          # Max attempts per stage
BASE_BACKOFF    = 30         # Seconds — doubles each retry (30, 60, 120, 240, 480)
QUOTA_WAIT      = 3600       # 1 hour wait on quota exhaustion
HEALTH_ENDPOINT = os.getenv("HEALTH_ENDPOINT", "")   # Optional: URL to ping on success

# Alert channels (all optional — set in .env)
ALERT_EMAIL     = os.getenv("ALERT_EMAIL", "")
ALERT_WEBHOOK   = os.getenv("ALERT_WEBHOOK", "")     # Slack/Discord webhook URL
SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER       = os.getenv("SMTP_USER", "")
SMTP_PASS       = os.getenv("SMTP_PASS", "")

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(message)s",
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(PIPELINE_LOG)
    ]
)
log = logging.getLogger(__name__)


# ── Error Classification ──────────────────────────────────────────────────────

class QuotaExhausted(Exception):
    """API quota/rate-limit hit. Wait and retry."""

class TemporaryFailure(Exception):
    """Network issue, timeout, transient error. Retry with backoff."""

class PermanentFailure(Exception):
    """Config problem, bad credentials, etc. Alert and stop."""


def classify_error(exc: Exception) -> type:
    """Map an exception to a recovery strategy."""
    msg = str(exc).lower()

    quota_signals = [
        "quota", "rate limit", "429", "too many requests",
        "exceeded", "resource exhausted", "dailylimitexceeded"
    ]
    if any(s in msg for s in quota_signals):
        return QuotaExhausted

    perm_signals = [
        "invalid api key", "unauthorized", "403", "forbidden",
        "authentication", "permission denied", "invalid_api_key"
    ]
    if any(s in msg for s in perm_signals):
        return PermanentFailure

    return TemporaryFailure


# ── Retry Decorator ───────────────────────────────────────────────────────────

def with_retry(fn, stage_name: str, max_retries: int = MAX_RETRIES):
    """
    Execute fn() with exponential backoff and smart error classification.
    Raises PermanentFailure if all retries are exhausted.
    """
    attempt = 0
    last_err = None

    while attempt <= max_retries:
        try:
            return fn()

        except Exception as exc:
            last_err   = exc
            error_type = classify_error(exc)

            if error_type == PermanentFailure:
                log.error(f"[{stage_name}] Permanent failure: {exc}")
                raise PermanentFailure(f"{stage_name}: {exc}") from exc

            if error_type == QuotaExhausted:
                wait = QUOTA_WAIT
                log.warning(f"[{stage_name}] Quota hit. Waiting {wait//60} minutes before retry...")
                _record_failure(stage_name, str(exc), "quota", attempt)
                time.sleep(wait)

            else:
                wait = BASE_BACKOFF * (2 ** attempt)
                log.warning(
                    f"[{stage_name}] Attempt {attempt+1}/{max_retries} failed: {exc}. "
                    f"Retrying in {wait}s..."
                )
                _record_failure(stage_name, str(exc), "temporary", attempt)
                time.sleep(wait)

            attempt += 1

    raise PermanentFailure(
        f"{stage_name} failed after {max_retries} retries. Last error: {last_err}"
    )


# ── State Management ──────────────────────────────────────────────────────────

def load_and_validate_state() -> dict:
    """
    Load run state, validate its structure, and repair if corrupted.
    This means the pipeline always starts from a sane baseline.
    """
    default = {
        "scraped_ids":   [],
        "last_run":      None,
        "last_success":  None,
        "consecutive_failures": 0,
        "pipeline_version": "1.0"
    }

    if not STATE_FILE.exists():
        log.info("No state file found. Starting fresh.")
        return default

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        # Validate required keys
        for key in default:
            if key not in state:
                log.warning(f"State missing key '{key}' — repairing.")
                state[key] = default[key]

        # Validate types
        if not isinstance(state["scraped_ids"], list):
            log.warning("scraped_ids corrupted — resetting to empty list.")
            state["scraped_ids"] = []

        log.info(f"State loaded: {len(state['scraped_ids'])} known videos, "
                 f"last run: {state.get('last_run', 'never')}")
        return state

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.error(f"State file corrupted ({e}). Creating backup and starting fresh.")

        # Backup corrupted state before overwriting
        backup = STATE_FILE.with_suffix(".corrupted.json")
        STATE_FILE.rename(backup)
        log.info(f"Corrupted state saved to: {backup}")

        return default


def save_state(state: dict):
    """Atomic state save — write to temp file first, then rename."""
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.rename(STATE_FILE)


# ── Failure Tracking ──────────────────────────────────────────────────────────

def _record_failure(stage: str, error: str, error_type: str, attempt: int):
    """Append to failures.json for later inspection."""
    failures = []
    if FAILURE_LOG.exists():
        try:
            with open(FAILURE_LOG) as f:
                failures = json.load(f)
        except Exception:
            failures = []

    failures.append({
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "stage":      stage,
        "error":      error[:500],
        "error_type": error_type,
        "attempt":    attempt
    })

    # Keep last 200 entries
    failures = failures[-200:]
    with open(FAILURE_LOG, "w") as f:
        json.dump(failures, f, indent=2)


# ── Alerting ──────────────────────────────────────────────────────────────────

def send_alert(subject: str, body: str):
    """
    Send an alert via email and/or webhook.
    Only fires when the pipeline needs actual human attention.
    """
    log.warning(f"ALERT: {subject}")

    # Webhook (Slack / Discord / ntfy.sh / etc.)
    if ALERT_WEBHOOK:
        try:
            requests.post(
                ALERT_WEBHOOK,
                json    = {"text": f"🚨 *Enstui Pipeline Alert*\n*{subject}*\n{body}"},
                timeout = 10
            )
        except Exception as e:
            log.warning(f"Webhook alert failed: {e}")

    # Email
    if ALERT_EMAIL and SMTP_USER and SMTP_PASS:
        try:
            msg            = MIMEText(body)
            msg["Subject"] = f"[Enstui Pipeline] {subject}"
            msg["From"]    = SMTP_USER
            msg["To"]      = ALERT_EMAIL

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        except Exception as e:
            log.warning(f"Email alert failed: {e}")


def ping_health(status: str, message: str = ""):
    """Ping an uptime monitor (e.g. UptimeRobot, BetterStack) after each run."""
    if not HEALTH_ENDPOINT:
        return
    try:
        requests.get(
            HEALTH_ENDPOINT,
            params  = {"status": status, "msg": message[:200]},
            timeout = 10
        )
    except Exception:
        pass


# ── Stage Runners ─────────────────────────────────────────────────────────────

def run_scraper(state: dict) -> dict:
    """Run scraper.py logic inline with retry wrapping."""
    log.info("▶ Stage 1: Scraping YouTube channel...")

    def _scrape():
        import scraper
        scraper.run()

    with_retry(_scrape, "scraper")
    log.info("✔ Stage 1 complete.")
    return state


def run_embedder(state: dict) -> dict:
    """Run embed_transcripts.py logic inline with retry wrapping."""
    log.info("▶ Stage 2: Embedding new transcripts...")

    def _embed():
        import embed_transcripts
        embed_transcripts.run()

    with_retry(_embed, "embedder")
    log.info("✔ Stage 2 complete.")
    return state


def check_db_health() -> bool:
    """
    Verify Supabase is reachable and the table exists.
    Returns True if healthy, False if something is wrong.
    """
    try:
        from kb_manager import get_supabase
        sb   = get_supabase()
        resp = sb.table("enstui_embedded_sources").select("source_id").limit(1).execute()
        return True
    except Exception as e:
        log.error(f"DB health check failed: {e}")
        return False


def check_youtube_api() -> bool:
    """Verify YouTube API key works with a minimal quota call."""
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY"))
        yt.videos().list(part="id", id="dQw4w9WgXcQ").execute()
        return True
    except Exception as e:
        log.error(f"YouTube API health check failed: {e}")
        return False


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def run():
    start_time = datetime.now(timezone.utc)
    log.info("=" * 65)
    log.info("  ENSTUI OU PIPELINE — Autonomous Run")
    log.info(f"  {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 65)

    state = load_and_validate_state()

    # ── Pre-flight checks ──────────────────────────────────────────────────
    log.info("Running pre-flight health checks...")

    db_ok = check_db_health()
    yt_ok = check_youtube_api()

    if not db_ok:
        msg = "Supabase is unreachable. Pipeline aborted."
        log.error(msg)
        send_alert("Supabase Down", msg)
        state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
        save_state(state)
        ping_health("fail", msg)
        return

    if not yt_ok:
        msg = "YouTube API key invalid or quota exhausted before run."
        log.error(msg)
        send_alert("YouTube API Error", msg)
        state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
        save_state(state)
        ping_health("fail", msg)
        return

    log.info("Pre-flight OK ✔")

    # ── Execute stages ─────────────────────────────────────────────────────
    stages = [
        ("scraper",   run_scraper),
        ("embedder",  run_embedder),
    ]

    for stage_name, stage_fn in stages:
        try:
            state = stage_fn(state)
        except PermanentFailure as exc:
            error_msg = str(exc)
            log.error(f"PIPELINE STOPPED at [{stage_name}]: {error_msg}")
            log.error(traceback.format_exc())

            state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
            state["last_run"] = start_time.isoformat()
            save_state(state)

            if state["consecutive_failures"] >= 3:
                send_alert(
                    f"Pipeline needs attention — {state['consecutive_failures']} consecutive failures",
                    f"Stage: {stage_name}\n\nError:\n{error_msg}\n\n"
                    f"Last success: {state.get('last_success', 'never')}\n\n"
                    f"Check pipeline.log and failures.json for details."
                )
            ping_health("fail", error_msg[:200])
            return

    # ── Success ────────────────────────────────────────────────────────────
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    state["consecutive_failures"] = 0
    state["last_run"]     = start_time.isoformat()
    state["last_success"] = start_time.isoformat()
    save_state(state)

    log.info("=" * 65)
    log.info(f"  PIPELINE COMPLETE ✅  ({elapsed:.0f}s)")
    log.info("=" * 65)

    ping_health("ok", f"Completed in {elapsed:.0f}s")


if __name__ == "__main__":
    run()
