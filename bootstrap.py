"""
bootstrap.py

ONE-TIME first-time setup wizard.
Run this once after cloning/downloading the project.
It handles everything automatically:

  1. Creates a virtual environment
  2. Installs all dependencies
  3. Validates your .env API keys (pauses if any are missing)
  4. Creates Supabase tables (gives instructions if manual needed)
  5. Scrapes the YouTube channel
  6. Embeds all transcripts
  7. Embeds any books in /books
  8. Launches the Streamlit app

VS Code: Press Ctrl+Shift+B  (or F5 with "Bootstrap" config selected)
Terminal: python bootstrap.py
"""

import os
import sys
import time
import subprocess
import shutil
from pathlib import Path

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
def step(n, msg): print(f"\n{GOLD}{BOLD}[{n}] {msg}{RESET}")
def banner(msg):
    print(f"\n{GOLD}{BOLD}{'═'*55}")
    print(f"  {msg}")
    print(f"{'═'*55}{RESET}")


# ── Step 1: Virtual environment ───────────────────────────────────────────────

def _venv_python_path() -> Path:
    """Return the expected venv python binary path for this platform."""
    mac_linux = Path(".venv/bin/python")
    if mac_linux.exists():
        return mac_linux
    windows = Path(".venv/Scripts/python.exe")
    if windows.exists():
        return windows
    return mac_linux  # default, caller checks .exists()


def _venv_has_pip(py: Path) -> bool:
    """Return True iff the given venv python has a working pip."""
    try:
        r = subprocess.run(
            [str(py), "-m", "pip", "--version"],
            capture_output=True, text=True
        )
        return r.returncode == 0
    except Exception:
        return False


def _create_venv() -> bool:
    """Create .venv (pip is included by default). Returns True on success."""
    info("Creating .venv (with pip)...")
    # Try with --upgrade-deps first (Python 3.9+)
    result = subprocess.run(
        [sys.executable, "-m", "venv", ".venv", "--upgrade-deps"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True
    # Older Python: retry without --upgrade-deps
    result = subprocess.run(
        [sys.executable, "-m", "venv", ".venv"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True
    warn(f"venv creation failed: {result.stderr.strip() or result.stdout.strip()}")
    return False


def _heal_venv_pip(py: Path) -> bool:
    """Try to install pip into an existing venv via ensurepip."""
    info("Repairing .venv (bootstrapping pip via ensurepip)...")
    r = subprocess.run(
        [str(py), "-m", "ensurepip", "--upgrade", "--default-pip"],
        capture_output=True, text=True
    )
    if r.returncode == 0 and _venv_has_pip(py):
        ok("pip bootstrapped into existing .venv")
        return True
    warn(f"ensurepip failed: {(r.stderr or r.stdout).strip()[:200]}")
    return False


def setup_venv():
    step("1/7", "Virtual Environment")
    venv = Path(".venv")

    if venv.exists():
        py = _venv_python_path()
        if py.exists() and _venv_has_pip(py):
            ok(".venv already exists and has working pip")
            return

        warn(".venv exists but has no working pip — attempting repair")

        # Attempt 1: ensurepip inside the existing venv
        if py.exists() and _heal_venv_pip(py):
            return

        # Attempt 2: wipe and rebuild
        info("Rebuilding .venv from scratch...")
        try:
            shutil.rmtree(venv)
        except Exception as e:
            fail(f"Could not delete broken .venv: {e}")
            info("Delete the .venv folder manually and re-run: python3 bootstrap.py")
            sys.exit(1)

    # Fresh create
    if not _create_venv():
        warn("Continuing without venv — using system Python")
        info("On Debian/Ubuntu: sudo apt install python3-venv  (then re-run bootstrap)")
        return

    py = _venv_python_path()
    if not _venv_has_pip(py):
        # Last resort: ensurepip on fresh venv
        if not _heal_venv_pip(py):
            fail(".venv was created but pip is missing and ensurepip failed")
            info("Try: python3 -m ensurepip --upgrade  (outside the project)")
            info("Or install python3-venv (Linux) / reinstall Python (Mac/Windows)")
            sys.exit(1)

    ok(".venv ready")
    info("NOTE: VS Code will auto-detect it. Restart the terminal if needed.")


def get_python():
    """Return path to the venv python or system python."""
    py = _venv_python_path()
    if py.exists():
        return str(py)
    return sys.executable


# ── Step 2: Install dependencies ──────────────────────────────────────────────

def install_deps():
    step("2/7", "Installing Dependencies")
    python = get_python()

    # Hard stop: if pip is missing here, nothing downstream will work
    probe = subprocess.run(
        [python, "-m", "pip", "--version"],
        capture_output=True, text=True
    )
    if probe.returncode != 0:
        fail("pip is not available in this Python environment")
        info("Fix: delete .venv and re-run bootstrap")
        info("  rm -rf .venv && python3 bootstrap.py")
        sys.exit(1)

    result = subprocess.run(
        [python, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ok("All packages installed")
    else:
        warn(f"Some packages failed: {result.stderr[:300]}")
        info("Retrying individually...")
        # Try installing one by one to isolate failures
        with open("requirements.txt") as f:
            packages = [
                # Strip inline `# comment` and whitespace so pip doesn't choke
                line.split("#", 1)[0].strip() for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
            packages = [p for p in packages if p]
        failed = []
        for pkg in packages:
            r = subprocess.run(
                [python, "-m", "pip", "install", pkg, "--quiet"],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                warn(f"  Could not install {pkg} — skipping")
                failed.append(pkg)
            else:
                ok(f"  {pkg}")

        if failed:
            fail(f"{len(failed)} package(s) failed to install")
            info("Bootstrap cannot proceed with broken dependencies.")
            info("Check your internet connection and re-run: python3 bootstrap.py")
            sys.exit(1)


# ── Step 3: Validate .env ────────────────────────────────────────────────────

def validate_env() -> bool:
    step("3/7", "API Keys (.env)")

    env_path     = Path(".env")
    example_path = Path(".env.example")

    if not env_path.exists():
        if example_path.exists():
            shutil.copy(example_path, env_path)
            ok("Created .env from .env.example")
        else:
            fail(".env file missing and no .env.example found")
            return False

    # Read the file directly (dotenv may not be installed yet)
    env_values = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env_values[k.strip()] = v.strip()

    required = [
        "YOUTUBE_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "GEMINI_API_KEY",
    ]

    def is_placeholder(v: str) -> bool:
        return (not v) or v.startswith("your_") or v.startswith("PASTE")

    missing = [k for k in required if is_placeholder(env_values.get(k, ""))]

    if missing:
        print(f"\n  {RED}{BOLD}⛔ Missing API keys in .env:{RESET}")
        for k in missing:
            print(f"     {YELLOW}{k}{RESET}")
        print(f"""
  {CYAN}What to do:{RESET}
  1. Open .env in VS Code  (it's in the project root)
  2. Replace each "PASTE_YOUR_..._HERE" placeholder with your real key
  3. Save the file
  4. Re-run: python bootstrap.py

  Where to get each key:
    YOUTUBE_API_KEY       → https://console.cloud.google.com (YouTube Data API v3)
    SUPABASE_URL          → https://app.supabase.com → Project Settings → API
    SUPABASE_SERVICE_KEY  → same page, use "service_role" key
    GEMINI_API_KEY        → https://aistudio.google.com/apikey  (free, no credit card)
""")
        return False

    ok("All API keys present")
    return True


# ── Step 4: Supabase setup ────────────────────────────────────────────────────

def setup_supabase() -> bool:
    step("4/7", "Supabase Database Setup")
    python = get_python()

    result = subprocess.run(
        [python, "-c",
         "from health import check_supabase; import sys; sys.exit(0 if check_supabase() else 1)"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ok("Supabase ready")
        return True
    else:
        print(result.stdout)
        warn("Supabase check had issues — see instructions above")
        print(f"\n  {YELLOW}Press ENTER once you've completed the Supabase SQL setup to continue...{RESET}")
        input()
        return True  # Trust the user and continue


# ── Step 5: Scrape channel ────────────────────────────────────────────────────

def run_scraper() -> bool:
    step("5/7", "Scraping YouTube Channel (@EnstuiOu)")
    python = get_python()

    # Check if we already have transcripts
    t_dir = Path("transcripts")
    existing = list(t_dir.glob("*.json")) if t_dir.exists() else []

    if existing:
        info(f"Found {len(existing)} existing transcript files")
        answer = input(f"  {CYAN}Scrape for new videos? (y/n, default y): {RESET}").strip().lower()
        if answer == "n":
            ok("Skipping scrape")
            return True

    info("Running scraper (this may take a few minutes for first run)...")
    result = subprocess.run([python, "scraper.py"])

    if result.returncode == 0:
        ok("Scrape complete")
        return True
    else:
        warn("Scraper exited with errors — check scraper.log")
        info("Common causes: YouTube API quota hit (resets midnight Pacific), bad API key")
        answer = input(f"  {CYAN}Continue anyway? (y/n): {RESET}").strip().lower()
        return answer != "n"


# ── Step 6: Embed transcripts ─────────────────────────────────────────────────

def run_embedder() -> bool:
    step("6/7", "Embedding Transcripts into Supabase")
    python = get_python()

    t_dir = Path("transcripts")
    files = [f for f in t_dir.glob("*.json") if "NO_TRANSCRIPT" not in f.name] if t_dir.exists() else []

    if not files:
        warn("No transcript files to embed — skipping")
        return True

    info(f"Embedding {len(files)} transcript files...")
    result = subprocess.run([python, "embed_transcripts.py"])

    if result.returncode == 0:
        ok("Embedding complete")
    else:
        warn("Embedder had errors — check embedder.log")

    # Embed books if any exist
    books_dir = Path("books")
    if books_dir.exists() and list(books_dir.glob("*.pdf")):
        info("Found PDFs in /books — embedding books too...")
        subprocess.run([python, "embed_books.py"])

    return True


# ── Step 7: Launch app ────────────────────────────────────────────────────────

def launch_app():
    step("7/7", "Launching Streamlit App")
    python = get_python()

    print(f"""
  {GREEN}{BOLD}✅  Setup complete!{RESET}

  {CYAN}The app will open at:{RESET}  http://localhost:8501
  {CYAN}Stop with:{RESET}            Ctrl+C

  {GOLD}Your advisor is powered by real @EnstuiOu channel content.{RESET}
""")

    time.sleep(1)
    subprocess.run([python, "run.py"])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    banner("ENSTUI OU — First Time Setup Wizard")
    print(f"  This wizard installs and configures the full system.\n")

    setup_venv()
    install_deps()

    if not validate_env():
        sys.exit(1)

    # Re-import health now that packages are installed
    if not setup_supabase():
        sys.exit(1)

    if not run_scraper():
        sys.exit(1)

    run_embedder()
    launch_app()


if __name__ == "__main__":
    main()
