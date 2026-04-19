"""
run.py

Smart orchestrator with self-healing watchdog.
Runs health checks, then launches the Streamlit app with
automatic restart if it crashes.

VS Code: Press F5 with "Run Orchestrator" config, or
         Ctrl+Shift+P → Tasks → "▶️  RUN — Launch App"
Terminal: python run.py
"""

import os
import sys
import time
import signal
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
GOLD   = "\033[33m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✔{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def fail(msg): print(f"  {RED}✘{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(message)s",
    handlers= [logging.FileHandler("run.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

MAX_RESTARTS     = 5       # How many times to restart Streamlit before giving up
RESTART_DELAY    = 3       # Seconds to wait between restart attempts
CRASH_THRESHOLD  = 10      # If app dies within this many seconds, count as crash
STREAMLIT_PORT   = 8501

app_process: subprocess.Popen = None


# ── Graceful shutdown ─────────────────────────────────────────────────────────

def shutdown(sig=None, frame=None):
    global app_process
    print(f"\n\n  {YELLOW}Shutting down...{RESET}")
    if app_process and app_process.poll() is None:
        app_process.terminate()
        try:
            app_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app_process.kill()
    log.info("Shutdown complete")
    sys.exit(0)

signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)


# ── Health pre-check ──────────────────────────────────────────────────────────

def quick_health_check() -> bool:
    """
    Fast check of critical dependencies before starting.
    Returns True if safe to launch, False if must abort.
    """
    print(f"\n{GOLD}{BOLD}  Pre-launch Health Check{RESET}")

    # 1. .env exists
    if not Path(".env").exists():
        fail(".env file missing — run 'python bootstrap.py' first")
        return False
    ok(".env found")

    # 2. Critical keys present
    critical_keys = ["GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    for key in critical_keys:
        val = os.getenv(key, "").strip()
        if not val or val.startswith("your_") or val.startswith("PASTE"):
            fail(f"{key} not set in .env")
            info("Open .env and add your API keys, then re-run")
            return False
    ok("API keys present")

    # 3. Packages importable
    for mod in ["streamlit", "supabase", "google.genai"]:
        try:
            __import__(mod)
        except ImportError:
            fail(f"{mod} not installed")
            info("Run: pip install -r requirements.txt")
            return False
    ok("Core packages installed")

    # 4. At least some data in DB
    try:
        from supabase import create_client
        sb    = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
        count = sb.table("enstui_chunks").select("id", count="exact").execute().count or 0
        if count == 0:
            warn("Knowledge base is empty — advisor will have no channel context")
            info("Run 'Step 2A — Embed Transcripts' from the VS Code task menu")
        else:
            ok(f"Knowledge base: {count:,} chunks ready")
    except Exception as e:
        warn(f"DB check failed: {e}")
        info("Run full health check: python health.py")

    return True


# ── Self-healing error classifier ─────────────────────────────────────────────

def classify_crash(return_code: int, log_tail: str) -> dict:
    """
    Given a crash, figure out what went wrong and suggest a fix.
    Returns {"reason": str, "auto_fix": callable or None, "fatal": bool}
    """
    log_lower = log_tail.lower()

    if "modulenotfounderror" in log_lower or "no module named" in log_lower:
        return {
            "reason":    "Missing Python package",
            "auto_fix":  lambda: subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]),
            "fatal":     False
        }

    if "connection refused" in log_lower or "could not connect" in log_lower:
        return {
            "reason":    "Supabase connection failed",
            "auto_fix":  None,
            "fatal":     False,
            "advice":    "Check SUPABASE_URL in .env — make sure it starts with https://"
        }

    if "invalid api key" in log_lower or "authentication" in log_lower or "401" in log_lower:
        return {
            "reason":    "Invalid API key",
            "auto_fix":  None,
            "fatal":     True,
            "advice":    "Check your API keys in .env — one of them is wrong or expired"
        }

    if "port" in log_lower and "already in use" in log_lower:
        return {
            "reason":    "Port 8501 already in use",
            "auto_fix":  lambda: subprocess.run(["pkill", "-f", "streamlit"]),
            "fatal":     False,
            "advice":    "Another Streamlit instance is running — killing it and retrying"
        }

    if "quota" in log_lower or "rate limit" in log_lower or "429" in log_lower:
        return {
            "reason":    "API rate limit / quota",
            "auto_fix":  None,
            "fatal":     False,
            "advice":    "Waiting 60 seconds before retry..."
        }

    if return_code == 0:
        return {"reason": "Clean exit", "auto_fix": None, "fatal": False}

    return {
        "reason":    f"Unknown crash (exit code {return_code})",
        "auto_fix":  None,
        "fatal":     False,
        "advice":    "Check run.log for details"
    }


# ── App launcher with watchdog ────────────────────────────────────────────────

def launch_streamlit() -> subprocess.Popen:
    """Start the Streamlit process and return the handle."""
    python = _get_python()
    cmd    = [
        python, "-m", "streamlit", "run", "app.py",
        "--server.port",         str(STREAMLIT_PORT),
        "--server.headless",     "true",
        "--browser.gatherUsageStats", "false",
        "--logger.level",        "warning",
    ]
    log.info(f"Launching: {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def _get_python() -> str:
    venv = Path(".venv/bin/python")
    if venv.exists():
        return str(venv)
    venv_win = Path(".venv/Scripts/python.exe")
    if venv_win.exists():
        return str(venv_win)
    return sys.executable


def read_log_tail(n: int = 50) -> str:
    """Read the last n lines from run.log for crash analysis."""
    log_path = Path("run.log")
    if not log_path.exists():
        return ""
    lines = log_path.read_text(errors="ignore").splitlines()
    return "\n".join(lines[-n:])


def run_with_watchdog():
    """
    Launch Streamlit and monitor it.
    If it crashes, diagnose the cause, apply auto-fix if available,
    and restart up to MAX_RESTARTS times.
    """
    global app_process

    restarts = 0

    while restarts <= MAX_RESTARTS:
        start_time = time.time()

        if restarts == 0:
            print(f"\n  {GREEN}{BOLD}✅  Launching Enstui Ou Advisor{RESET}")
            print(f"  {CYAN}Open your browser:{RESET}  http://localhost:{STREAMLIT_PORT}")
            print(f"  {CYAN}Stop:{RESET}               Ctrl+C\n")
        else:
            print(f"\n  {YELLOW}⟳  Restarting... (attempt {restarts}/{MAX_RESTARTS}){RESET}\n")

        app_process = launch_streamlit()
        app_process.wait()    # Block until it exits

        elapsed     = time.time() - start_time
        return_code = app_process.returncode
        log_tail    = read_log_tail()
        crash       = classify_crash(return_code, log_tail)

        if return_code == 0 or crash["fatal"]:
            if crash["fatal"]:
                fail(f"Fatal error: {crash['reason']}")
                if "advice" in crash:
                    info(crash["advice"])
            break

        restarts += 1
        warn(f"App exited (code {return_code}) — {crash['reason']}")

        if "advice" in crash:
            info(crash["advice"])

        # Apply auto-fix if available
        if crash.get("auto_fix"):
            info("Applying auto-fix...")
            try:
                crash["auto_fix"]()
                ok("Auto-fix applied")
            except Exception as e:
                warn(f"Auto-fix failed: {e}")

        # Extra wait for rate limits
        delay = 60 if "rate limit" in crash["reason"].lower() else RESTART_DELAY
        if elapsed < CRASH_THRESHOLD:
            warn(f"App crashed quickly ({elapsed:.1f}s) — waiting {delay}s before retry")
            time.sleep(delay)
        else:
            time.sleep(RESTART_DELAY)

    if restarts > MAX_RESTARTS:
        fail(f"App crashed {MAX_RESTARTS} times in a row. Stopping.")
        info("Run 'python health.py' for a full diagnosis")
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{GOLD}{BOLD}{'═'*55}")
    print("  ENSTUI OU — Run Orchestrator")
    print(f"{'═'*55}{RESET}")

    if not quick_health_check():
        print(f"\n  {RED}Fix the issues above, then re-run: python run.py{RESET}\n")
        sys.exit(1)

    run_with_watchdog()


if __name__ == "__main__":
    main()
