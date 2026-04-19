#!/usr/bin/env python3
"""
setup_and_run.py

THE MASTER ORCHESTRATOR
━━━━━━━━━━━━━━━━━━━━━━━
This single script handles:
  1. Full first-time setup (--setup)
  2. Health checks on every startup (--check-only)
  3. Self-healing when anything breaks (--heal)
  4. Running all pipeline steps (--run-scraper, --run-embedder)

Firebase Studio calls this automatically via dev.nix.
You can also call it manually:

    python setup_and_run.py --setup       Full install + configure
    python setup_and_run.py --check-only  Fast health check, auto-heal if broken
    python setup_and_run.py --heal        Force re-heal everything
    python setup_and_run.py --run-scraper Run Step 1 (YouTube scrape)
    python setup_and_run.py --run-embed   Run Step 2 (embed to Supabase)
    python setup_and_run.py --status      Show system status dashboard
"""

import os
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt= "%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("system.log", mode="a")
    ]
)
log = logging.getLogger("orchestrator")

# ── Constants ─────────────────────────────────────────────────────────────────

VENV_DIR       = Path(".venv")
REQ_FILE       = Path("requirements.txt")
ENV_FILE       = Path(".env")
ENV_EXAMPLE    = Path(".env.example")
STATE_FILE     = Path("last_run_state.json")
TRANSCRIPTS    = Path("transcripts")
BOOKS_DIR      = Path("books")
HEALTH_FILE    = Path(".health_status.json")

REQUIRED_ENV_VARS = [
    "YOUTUBE_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "GEMINI_API_KEY",
]

REQUIRED_PYTHON_PACKAGES = [
    "google-api-python-client",
    "youtube-transcript-api",
    "google-genai",
    "supabase",
    "tiktoken",
    "pypdf",
    "streamlit",
    "python-dotenv",
]

# ── Colors for terminal output ────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   log.info(f"{GREEN}✔  {msg}{RESET}")
def warn(msg): log.warning(f"{YELLOW}⚠  {msg}{RESET}")
def err(msg):  log.error(f"{RED}✘  {msg}{RESET}")
def info(msg): log.info(f"{BLUE}→  {msg}{RESET}")
def head(msg): log.info(f"\n{BOLD}{'─'*55}\n  {msg}\n{'─'*55}{RESET}")

# ── Health State ──────────────────────────────────────────────────────────────

def load_health() -> dict:
    if HEALTH_FILE.exists():
        try:
            return json.loads(HEALTH_FILE.read_text())
        except Exception:
            pass
    return {}


def save_health(state: dict):
    HEALTH_FILE.write_text(json.dumps(state, indent=2))


# ── Check: Virtual Environment ────────────────────────────────────────────────

def check_venv() -> bool:
    return (VENV_DIR / "bin" / "python").exists() or (VENV_DIR / "Scripts" / "python.exe").exists()


def heal_venv():
    info("Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        ok("Virtual environment created.")
        return True
    except subprocess.CalledProcessError as e:
        err(f"venv creation failed: {e}")
        return False


# ── Check: Python Packages ────────────────────────────────────────────────────

def get_venv_python() -> str:
    candidates = [
        VENV_DIR / "bin" / "python",
        VENV_DIR / "Scripts" / "python.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return sys.executable


def check_packages() -> tuple[bool, list]:
    """Returns (all_ok, list_of_missing)"""
    python = get_venv_python()
    missing = []

    for pkg in REQUIRED_PYTHON_PACKAGES:
        import_name = pkg.replace("-", "_").split("==")[0]
        # Handle special cases
        if import_name == "google_api_python_client":
            import_name = "googleapiclient"
        elif import_name == "youtube_transcript_api":
            import_name = "youtube_transcript_api"
        elif import_name == "python_dotenv":
            import_name = "dotenv"

        result = subprocess.run(
            [python, "-c", f"import {import_name}"],
            capture_output=True
        )
        if result.returncode != 0:
            missing.append(pkg)

    return len(missing) == 0, missing


def heal_packages(missing: list = None):
    python = get_venv_python()
    pip    = str(VENV_DIR / "bin" / "pip") if (VENV_DIR / "bin" / "pip").exists() \
             else str(VENV_DIR / "Scripts" / "pip.exe")

    info(f"Installing Python packages from {REQ_FILE}...")
    try:
        result = subprocess.run(
            [pip, "install", "-r", str(REQ_FILE), "--quiet"],
            check=True, capture_output=True, text=True
        )
        ok("All packages installed.")
        return True
    except subprocess.CalledProcessError as e:
        err(f"pip install failed:\n{e.stderr}")
        # Try installing missing packages one by one as fallback
        if missing:
            warn("Trying individual package installs as fallback...")
            failed = []
            for pkg in missing:
                try:
                    subprocess.run([pip, "install", pkg, "--quiet"], check=True)
                    ok(f"  Installed: {pkg}")
                except subprocess.CalledProcessError:
                    failed.append(pkg)
                    err(f"  Failed: {pkg}")
            return len(failed) == 0
        return False


# ── Check: .env File ─────────────────────────────────────────────────────────

def check_env() -> tuple[bool, list]:
    """Returns (all_keys_present, list_of_missing_keys)"""
    if not ENV_FILE.exists():
        return False, REQUIRED_ENV_VARS

    # Load .env manually (dotenv may not be installed yet)
    env_values = {}
    try:
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env_values[key.strip()] = val.strip()
    except Exception:
        return False, REQUIRED_ENV_VARS

    missing = []
    for var in REQUIRED_ENV_VARS:
        val = env_values.get(var, "").strip()
        if not val or val.startswith("your_") or val == "":
            missing.append(var)

    return len(missing) == 0, missing


def heal_env():
    """Create .env from .env.example if it doesn't exist."""
    if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        warn(f".env created from .env.example")
        warn("⚠️  IMPORTANT: Open .env and fill in your API keys before running the app.")
    elif not ENV_FILE.exists():
        # Create a blank .env with placeholders
        content = "\n".join(f"{v}=your_{v.lower()}_here" for v in REQUIRED_ENV_VARS)
        ENV_FILE.write_text(content + "\n")
        warn(".env created with placeholders — fill in your API keys.")


# ── Check: Directories ────────────────────────────────────────────────────────

def check_directories() -> bool:
    for d in [TRANSCRIPTS, BOOKS_DIR]:
        if not d.exists():
            return False
    return True


def heal_directories():
    TRANSCRIPTS.mkdir(exist_ok=True)
    BOOKS_DIR.mkdir(exist_ok=True)
    # Add .gitkeep so empty dirs are tracked
    (TRANSCRIPTS / ".gitkeep").touch()
    (BOOKS_DIR / ".gitkeep").touch()
    ok("Directories created: transcripts/, books/")


# ── Check: Supabase Connectivity ─────────────────────────────────────────────

def check_supabase_connection() -> tuple[bool, str]:
    """Try to reach Supabase and verify the table exists."""
    python = get_venv_python()

    test_script = """
import os, sys
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("SUPABASE_URL", "")
key = os.getenv("SUPABASE_SERVICE_KEY", "")

if not url or url.startswith("your_"):
    print("NOT_CONFIGURED")
    sys.exit(0)

try:
    from supabase import create_client
    sb = create_client(url, key)
    # Try to query the table
    sb.table("enstui_chunks").select("id").limit(1).execute()
    print("OK")
except Exception as e:
    err_str = str(e)
    if "relation" in err_str and "does not exist" in err_str:
        print("TABLE_MISSING")
    elif "Invalid API key" in err_str or "401" in err_str:
        print("INVALID_KEY")
    else:
        print(f"ERROR:{err_str[:100]}")
"""
    try:
        result = subprocess.run(
            [python, "-c", test_script],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout.strip()
        return output == "OK", output
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"ERROR:{e}"


# ── Full Health Check ────────────────────────────────────────────────────────

def run_health_check(auto_heal: bool = True) -> dict:
    head("System Health Check")
    results = {}
    all_ok  = True

    # 1. Virtual environment
    if check_venv():
        ok("Virtual environment")
        results["venv"] = "ok"
    else:
        warn("Virtual environment missing")
        results["venv"] = "missing"
        all_ok = False
        if auto_heal:
            if heal_venv():
                results["venv"] = "healed"
            else:
                results["venv"] = "failed"

    # 2. Python packages
    pkgs_ok, missing_pkgs = check_packages()
    if pkgs_ok:
        ok("Python packages")
        results["packages"] = "ok"
    else:
        warn(f"Missing packages: {', '.join(missing_pkgs[:5])}")
        results["packages"] = "missing"
        all_ok = False
        if auto_heal:
            if heal_packages(missing_pkgs):
                results["packages"] = "healed"
            else:
                results["packages"] = "failed"

    # 3. .env file
    env_ok, missing_keys = check_env()
    if env_ok:
        ok(".env file — all keys present")
        results["env"] = "ok"
    else:
        if not ENV_FILE.exists():
            warn(".env file missing")
            results["env"] = "missing"
            if auto_heal:
                heal_env()
                results["env"] = "created_needs_keys"
        else:
            warn(f".env missing values for: {', '.join(missing_keys)}")
            results["env"] = f"missing_keys:{','.join(missing_keys)}"
        all_ok = False

    # 4. Directories
    if check_directories():
        ok("Required directories (transcripts/, books/)")
        results["dirs"] = "ok"
    else:
        warn("Required directories missing")
        results["dirs"] = "missing"
        if auto_heal:
            heal_directories()
            results["dirs"] = "healed"

    # 5. Supabase connectivity (only if keys are present)
    if env_ok:
        info("Checking Supabase connection...")
        sb_ok, sb_status = check_supabase_connection()
        if sb_ok:
            ok("Supabase — connected and table found")
            results["supabase"] = "ok"
        elif sb_status == "TABLE_MISSING":
            warn("Supabase connected but tables not set up yet")
            warn("→ Run supabase_setup.sql in your Supabase SQL Editor (one-time step)")
            results["supabase"] = "table_missing"
            all_ok = False
        elif sb_status == "NOT_CONFIGURED":
            warn("Supabase not configured (keys are placeholders)")
            results["supabase"] = "not_configured"
            all_ok = False
        else:
            warn(f"Supabase issue: {sb_status}")
            results["supabase"] = f"error:{sb_status}"
            all_ok = False
    else:
        results["supabase"] = "skipped_no_keys"

    # ── Summary ──────────────────────────────────────────────────────────────
    log.info("")
    if all_ok:
        ok(f"{BOLD}All systems operational. Ready to launch.{RESET}")
    else:
        if results.get("env") in ("missing", "created_needs_keys") or \
           "missing_keys" in str(results.get("env", "")):
            log.info(f"\n{YELLOW}{BOLD}ACTION REQUIRED:{RESET}")
            log.info(f"{YELLOW}  Open the .env file and add your API keys.")
            log.info(f"  Then re-run: python setup_and_run.py --check-only{RESET}\n")
        elif results.get("supabase") == "table_missing":
            log.info(f"\n{YELLOW}{BOLD}ACTION REQUIRED:{RESET}")
            log.info(f"{YELLOW}  1. Go to your Supabase project → SQL Editor")
            log.info(f"  2. Paste the contents of supabase_setup.sql")
            log.info(f"  3. Click Run")
            log.info(f"  Then re-run: python setup_and_run.py --check-only{RESET}\n")

    results["all_ok"]    = all_ok
    results["timestamp"] = datetime.now().isoformat()
    save_health(results)
    return results


# ── Full Setup (first-time) ───────────────────────────────────────────────────

def run_setup():
    head("Enstui Ou — First-Time Setup")
    info("This runs once. Next time the workspace opens, it just checks health.\n")

    # Step 1: Directories
    heal_directories()

    # Step 2: Virtual environment
    if not check_venv():
        if not heal_venv():
            err("Cannot create virtual environment. Check Python installation.")
            sys.exit(1)

    # Step 3: Install packages
    pkgs_ok, missing = check_packages()
    if not pkgs_ok:
        if not heal_packages(missing):
            err("Package installation failed. Check requirements.txt.")
            sys.exit(1)

    # Step 4: .env setup
    env_ok, missing_keys = check_env()
    if not env_ok:
        heal_env()

    # Step 5: Run health check
    results = run_health_check(auto_heal=False)

    # Print setup completion
    head("Setup Complete")
    log.info(f"""
{GREEN}{BOLD}✔ Environment ready.{RESET}

{BOLD}Next steps:{RESET}

  1. {YELLOW}Add your API keys{RESET} to the .env file:
     Open .env in the editor and fill in each value.

  2. {YELLOW}Set up Supabase tables{RESET} (one-time):
     Copy supabase_setup.sql → paste into Supabase SQL Editor → Run.

  3. {YELLOW}Run the pipeline:{RESET}
     make scrape       # Pull all YouTube videos
     make embed        # Embed transcripts into Supabase
     make books        # Embed any PDFs in the books/ folder
     make run          # Launch the Streamlit advisor app

  Or just open the Preview panel — it starts the app automatically.

{BOLD}Self-healing:{RESET}
  If something breaks at any time, run:
     python setup_and_run.py --heal
  or
     make heal
""")


# ── Status Dashboard ─────────────────────────────────────────────────────────

def show_status():
    head("Enstui Ou — System Status")

    # Load health cache
    health = load_health()
    if health:
        info(f"Last check: {health.get('timestamp', 'unknown')}")

    # Count transcripts
    transcript_count = len(list(TRANSCRIPTS.glob("*.json"))) if TRANSCRIPTS.exists() else 0
    no_trans_count   = len(list(TRANSCRIPTS.glob("*_NO_TRANSCRIPT.json"))) if TRANSCRIPTS.exists() else 0
    good_trans       = transcript_count - no_trans_count

    # Count books
    book_count = len(list(BOOKS_DIR.glob("*.pdf"))) if BOOKS_DIR.exists() else 0

    # State file
    last_scrape = "Never"
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            last_scrape = state.get("last_run", "Never")[:19].replace("T", " ")
        except Exception:
            pass

    log.info(f"""
  📺  Transcripts:    {good_trans} with text  |  {no_trans_count} no-caption
  📚  Book PDFs:      {book_count} files in books/
  🕐  Last scrape:    {last_scrape}
  🗂  Venv:           {'✔' if check_venv() else '✘'}
  📄  .env:           {'✔' if ENV_FILE.exists() else '✘ — run: cp .env.example .env'}
""")

    # Overall health
    env_ok, missing = check_env()
    if not env_ok:
        warn(f"Missing API keys in .env: {', '.join(missing)}")
    else:
        ok("All API keys present in .env")


# ── Run Pipeline Steps ────────────────────────────────────────────────────────

def run_step(script_name: str, description: str, max_retries: int = 2):
    head(f"Running: {description}")
    python = get_venv_python()

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            warn(f"Retry {attempt}/{max_retries}...")
            time.sleep(3)

        try:
            result = subprocess.run(
                [python, script_name],
                check=True
            )
            ok(f"{description} completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            err(f"Attempt {attempt} failed (exit code {e.returncode})")

            # Auto-heal: reinstall packages and retry
            if attempt < max_retries:
                info("Auto-healing: reinstalling packages...")
                heal_packages()

    err(f"{description} failed after {max_retries} attempts.")
    err("Run 'python setup_and_run.py --heal' for a full environment reset.")
    return False


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enstui Ou Master Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_and_run.py --setup        First-time install
  python setup_and_run.py --check-only   Health check + auto-heal
  python setup_and_run.py --heal         Force full re-heal
  python setup_and_run.py --run-scraper  Run YouTube scraper
  python setup_and_run.py --run-embed    Run transcript embedder
  python setup_and_run.py --status       Show system status
"""
    )
    parser.add_argument("--setup",       action="store_true", help="Full first-time setup")
    parser.add_argument("--check-only",  action="store_true", help="Health check + auto-heal")
    parser.add_argument("--heal",        action="store_true", help="Force full re-heal")
    parser.add_argument("--run-scraper", action="store_true", help="Run YouTube scraper")
    parser.add_argument("--run-embed",   action="store_true", help="Run embedder")
    parser.add_argument("--run-books",   action="store_true", help="Run book embedder")
    parser.add_argument("--status",      action="store_true", help="Show status dashboard")

    args = parser.parse_args()

    if args.setup:
        run_setup()

    elif args.check_only:
        results = run_health_check(auto_heal=True)
        if not results["all_ok"]:
            sys.exit(1)

    elif args.heal:
        head("Force Heal — Resetting Environment")
        # Wipe venv and reinstall
        if VENV_DIR.exists():
            info("Removing existing virtual environment...")
            shutil.rmtree(VENV_DIR)
        heal_venv()
        heal_packages()
        heal_directories()
        env_ok, _ = check_env()
        if not env_ok:
            heal_env()
        run_health_check(auto_heal=False)

    elif args.run_scraper:
        run_health_check(auto_heal=True)
        run_step("scraper.py", "YouTube Channel Scraper")

    elif args.run_embed:
        run_health_check(auto_heal=True)
        run_step("embed_transcripts.py", "Transcript Embedder")

    elif args.run_books:
        run_health_check(auto_heal=True)
        run_step("embed_books.py", "Book Embedder")

    elif args.status:
        show_status()

    else:
        # Default: show help + status
        parser.print_help()
        log.info("")
        show_status()


if __name__ == "__main__":
    main()
