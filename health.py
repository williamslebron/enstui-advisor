"""
health.py

System health checker and self-repair tool.
Checks every component, explains exactly what is wrong, and auto-fixes
what it can. Used by bootstrap.py and run.py before every start.

Run standalone:
    python health.py
"""

import os
import sys
import subprocess
import importlib
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

def ok(msg):    print(f"  {GREEN}✔{RESET}  {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET}  {msg}")
def fail(msg):  print(f"  {RED}✘{RESET}  {msg}")
def info(msg):  print(f"  {CYAN}→{RESET}  {msg}")
def head(msg):  print(f"\n{GOLD}{BOLD}{msg}{RESET}")


# ── Required packages ─────────────────────────────────────────────────────────

REQUIRED_PACKAGES = {
    "google-api-python-client": "googleapiclient",
    "youtube-transcript-api":   "youtube_transcript_api",
    "python-dotenv":            "dotenv",
    "google-genai":             "google.genai",
    "supabase":                 "supabase",
    "tiktoken":                 "tiktoken",
    "pypdf":                    "pypdf",
    "streamlit":                "streamlit",
}

# ── Required env vars ─────────────────────────────────────────────────────────

REQUIRED_ENV = {
    "YOUTUBE_API_KEY":      "Get from https://console.cloud.google.com → APIs → YouTube Data API v3",
    "SUPABASE_URL":         "Get from https://app.supabase.com → Project Settings → API",
    "SUPABASE_SERVICE_KEY": "Get from https://app.supabase.com → Project Settings → API (service_role key)",
    "GEMINI_API_KEY":       "Get free key from https://aistudio.google.com/apikey",
}


# ── Check: Python version ─────────────────────────────────────────────────────

def check_python() -> bool:
    head("Python Version")
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 10:
        ok(f"Python {major}.{minor} ✓ (3.10+ required)")
        return True
    else:
        fail(f"Python {major}.{minor} found — need 3.10 or higher")
        info("Download: https://www.python.org/downloads/")
        return False


# ── Check: .env file ──────────────────────────────────────────────────────────

def check_env_file() -> bool:
    head(".env File")
    env_path     = Path(".env")
    example_path = Path(".env.example")

    if not env_path.exists():
        if example_path.exists():
            import shutil
            shutil.copy(example_path, env_path)
            warn(".env not found — created from .env.example")
            warn("OPEN .env AND FILL IN YOUR API KEYS, then re-run.")
        else:
            fail(".env file missing")
        return False

    ok(".env file exists")
    return True


# ── Check: API keys ───────────────────────────────────────────────────────────

def check_env_vars() -> tuple[bool, list[str]]:
    head("API Keys (.env)")
    missing = []
    all_ok  = True

    for var, instructions in REQUIRED_ENV.items():
        val = os.getenv(var, "").strip()
        if not val or val.startswith("your_") or val.startswith("PASTE_"):
            fail(f"{var} — NOT SET")
            info(instructions)
            missing.append(var)
            all_ok = False
        else:
            masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "****"
            ok(f"{var} = {masked}")

    return all_ok, missing


# ── Check + Auto-Install: Python packages ─────────────────────────────────────

def check_and_install_packages() -> bool:
    head("Python Packages")
    missing_installs = []
    all_ok           = True

    for pip_name, import_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
            ok(f"{pip_name}")
        except ImportError:
            warn(f"{pip_name} — NOT INSTALLED (auto-installing...)")
            missing_installs.append(pip_name)
            all_ok = False

    if missing_installs:
        info(f"Installing: {', '.join(missing_installs)}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing_installs,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok("All missing packages installed successfully")
            all_ok = True
        else:
            fail(f"Install failed:\n{result.stderr}")
            info("Try manually: pip install -r requirements.txt")
            all_ok = False

    return all_ok


# ── Check: Supabase connection + tables ───────────────────────────────────────

def check_supabase() -> bool:
    head("Supabase Connection")

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

    if not url or not key or url.startswith("your_") or url.startswith("PASTE"):
        warn("Skipping — SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
        return False

    try:
        from supabase import create_client
        sb = create_client(url, key)

        sb.table("enstui_embedded_sources").select("id").limit(1).execute()
        ok("Connected to Supabase")

        result = sb.table("enstui_chunks").select("id", count="exact").execute()
        count  = result.count or 0
        if count > 0:
            ok(f"enstui_chunks table exists — {count:,} chunks indexed")
        else:
            warn("enstui_chunks table exists but is EMPTY")
            info("Run 'python embed_transcripts.py' to populate it")

        return True

    except Exception as e:
        err = str(e)
        if "relation" in err and "does not exist" in err:
            fail("Tables not found in Supabase")
            info("Open Supabase → SQL Editor → paste supabase_setup.sql → Run")
            return False
        elif "Invalid API key" in err or "401" in err:
            fail("Invalid Supabase credentials")
            info("Check SUPABASE_SERVICE_KEY — use the service_role key, NOT anon")
            return False
        else:
            fail(f"Supabase error: {err}")
            return False


# ── Check: Gemini connectivity ────────────────────────────────────────────────

def check_gemini() -> bool:
    head("Gemini API")

    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("your_") or key.startswith("PASTE"):
        warn("Skipping — GEMINI_API_KEY not set")
        return False

    try:
        from google import genai
        client = genai.Client(api_key=key)

        # Cheap test 1: embed a single word
        embed_model = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")
        client.models.embed_content(model=embed_model, contents=["test"])

        # Cheap test 2: tiny chat
        chat_model = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
        resp = client.models.generate_content(
            model    = chat_model,
            contents = "ping",
        )
        _ = resp.text   # just make sure it comes back

        ok(f"Gemini API connected — {chat_model} + {embed_model} ready")
        return True

    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "401" in err or "invalid" in err.lower():
            fail("Invalid Gemini API key")
            info("Get a free key at https://aistudio.google.com/apikey")
        elif "429" in err or "quota" in err.lower() or "RATE_LIMIT" in err:
            warn("Gemini rate/quota limit hit — will retry automatically during operation")
            return True
        else:
            fail(f"Gemini error: {err}")
        return False


# ── Check: YouTube API ────────────────────────────────────────────────────────

def check_youtube() -> bool:
    head("YouTube Data API")

    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key or key.startswith("your_") or key.startswith("PASTE"):
        warn("Skipping — YOUTUBE_API_KEY not set")
        return False

    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", developerKey=key)
        yt.search().list(q="test", part="id", maxResults=1).execute()
        ok("YouTube Data API connected")
        return True

    except Exception as e:
        err = str(e)
        if "400" in err or "API key not valid" in err:
            fail("Invalid YouTube API key")
            info("Enable YouTube Data API v3 at https://console.cloud.google.com")
        elif "quota" in err.lower() or "403" in err:
            warn("YouTube API quota exceeded for today — resets at midnight Pacific")
            return True
        else:
            fail(f"YouTube API error: {err}")
        return False


# ── Check: transcript files ───────────────────────────────────────────────────

def check_transcripts() -> None:
    head("Local Transcript Files")
    t_dir = Path("transcripts")

    if not t_dir.exists() or not list(t_dir.glob("*.json")):
        warn("No transcripts found locally")
        info("Run 'python scraper.py' to download them")
        return

    files      = list(t_dir.glob("*.json"))
    no_trans   = [f for f in files if "NO_TRANSCRIPT" in f.name]
    with_trans = [f for f in files if "NO_TRANSCRIPT" not in f.name]

    ok(f"{len(with_trans)} transcript files ready")
    if no_trans:
        warn(f"{len(no_trans)} videos have no captions — run whisper_fallback.py to fix")


# ── Full report ───────────────────────────────────────────────────────────────

def run_health_check(auto_fix: bool = True) -> dict:
    print(f"\n{GOLD}{BOLD}{'═'*55}")
    print("  ENSTUI OU — System Health Check")
    print(f"{'═'*55}{RESET}")

    results = {}

    results["python"]   = check_python()
    results["env_file"] = check_env_file()

    load_dotenv(override=True)

    env_ok, missing = check_env_vars()
    results["env_vars"] = env_ok

    if missing:
        print(f"\n{RED}{BOLD}  ⛔ STOP: Fill in your API keys in .env before continuing.{RESET}")
        print(f"  Open .env in VS Code and replace all placeholder values.\n")
        return results

    results["packages"] = check_and_install_packages()
    results["supabase"] = check_supabase()
    results["gemini"]   = check_gemini()
    results["youtube"]  = check_youtube()
    check_transcripts()

    head("Summary")
    critical = ["python", "env_vars", "packages", "supabase", "gemini"]
    all_critical_ok = all(results.get(k, False) for k in critical)

    if all_critical_ok:
        print(f"\n  {GREEN}{BOLD}✅  All systems operational. Ready to run.{RESET}\n")
    else:
        failed = [k for k in critical if not results.get(k, False)]
        print(f"\n  {RED}{BOLD}❌  Issues found: {', '.join(failed)}{RESET}")
        print(f"  {YELLOW}Fix the issues above, then re-run: python health.py{RESET}\n")

    return results


if __name__ == "__main__":
    results = run_health_check()
    sys.exit(0 if all(results.values()) else 1)
