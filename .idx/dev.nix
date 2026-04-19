# .idx/dev.nix
#
# Firebase Studio / Google Antigravity — Workspace Configuration
# Enstui Ou Strategic Advisor System
#
# This file declares the ENTIRE environment:
#   - All system packages (Python, ffmpeg, etc.)
#   - All VS Code extensions
#   - Auto-setup on first open (onCreate)
#   - Auto-start on every open (onStart)
#   - Live Streamlit preview in the browser panel
#
# HOW TO USE:
#   1. Import this repo into Firebase Studio (studio.firebase.google.com)
#   2. Add your API keys in the workspace Secrets panel (see below)
#   3. Everything else runs automatically — no terminal commands needed.
#
# REQUIRED SECRETS (add in Firebase Studio → Settings → Secrets):
#   YOUTUBE_API_KEY       → Google Cloud Console → YouTube Data API v3
#   OPENAI_API_KEY        → platform.openai.com → API Keys
#   SUPABASE_URL          → supabase.com → Project Settings → API
#   SUPABASE_SERVICE_KEY  → supabase.com → Project Settings → API (service_role)
#   ANTHROPIC_API_KEY     → console.anthropic.com → API Keys

{ pkgs, ... }: {

  # ── Nixpkgs Channel ─────────────────────────────────────────────────────────
  channel = "stable-24.11";

  # ── System Packages ──────────────────────────────────────────────────────────
  # Everything the system needs — installed automatically, no apt-get required.
  packages = [
    pkgs.python311          # Python runtime
    pkgs.python311Packages.pip
    pkgs.python311Packages.virtualenv
    pkgs.ffmpeg             # Audio processing (Whisper fallback)
    pkgs.git                # Version control
    pkgs.curl               # Health checks
    pkgs.jq                 # JSON parsing in shell scripts
    pkgs.gnumake            # Make commands
  ];

  # ── Environment Variables ────────────────────────────────────────────────────
  # Non-secret environment defaults. Secrets are injected separately.
  env = {
    PYTHONUNBUFFERED = "1";    # Makes Python logs appear immediately
    PYTHONDONTWRITEBYTECODE = "1";
    STREAMLIT_SERVER_HEADLESS = "true";
    STREAMLIT_SERVER_ENABLE_CORS = "false";
    STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false";
    APP_ENV = "firebase_studio";
  };

  # ── VS Code Extensions ───────────────────────────────────────────────────────
  idx.extensions = [
    "ms-python.python"           # Python language support
    "ms-python.pylint"           # Linting
    "ms-python.black-formatter"  # Auto-formatting
    "ms-toolsai.jupyter"         # Jupyter notebooks
    "tamasfe.even-better-toml"   # TOML syntax
    "dotenv.dotenv-vscode"       # .env file support
    "eamodio.gitlens"            # Git blame / history
    "mhutchie.git-graph"         # Git graph viewer
    "streetsidesoftware.code-spell-checker"
  ];

  # ── Previews ─────────────────────────────────────────────────────────────────
  # Streamlit app will appear in the Firebase Studio Preview panel automatically.
  idx.previews = {
    enable = true;
    previews = {
      web = {
        command = [
          "bash" "-c"
          # Run setup first (idempotent), then start Streamlit
          "python setup_and_run.py --check-only || python setup_and_run.py --setup && streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"
        ];
        manager = "web";
        env = {
          PORT = "8080";
        };
      };
    };
  };

  # ── Workspace Lifecycle Hooks ────────────────────────────────────────────────
  idx.workspace = {

    # onCreate: Runs ONCE when the workspace is first created.
    # This is where the full bootstrap happens.
    onCreate = {
      full-setup = "python setup_and_run.py --setup";

      # Open the most important files so the dev knows where to look
      default.openFiles = [
        "app.py"
        ".env.example"
        "README_FIREBASE_STUDIO.md"
      ];
    };

    # onStart: Runs EVERY TIME the workspace opens.
    # Lighter check — only verifies env and starts watchers.
    onStart = {
      health-check  = "python setup_and_run.py --check-only";
      start-scraper = "echo 'Ready. Run: make scrape  or  make embed  or  streamlit run app.py'";
    };
  };
}
