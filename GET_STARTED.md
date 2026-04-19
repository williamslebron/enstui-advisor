# Get Started — Enstui Ou Strategic Advisor (Gemini Edition)

A single walkthrough from zero to a running app on your Mac or PC.
Total time: about 20 minutes, most of which is waiting on signups.

---

## What you are building

A local chat app at http://localhost:8501 that answers questions using the real
content of the @EnstuiOu YouTube channel plus any books you upload. The first run
scrapes the channel, embeds everything into a Supabase vector database, and
launches a Streamlit web app that uses Google Gemini as the advisor brain.

---

## Before you start

You need three free accounts. None of them require a credit card.

1. Google (used for both YouTube scraping and Gemini AI)
2. Supabase (vector database — free tier is plenty)

That's it. No OpenAI, no Anthropic, no billing.

---

## Step 0 — Install the tools on your computer

You need Python 3.10 or newer, and VS Code. Open a terminal and run the check:

```bash
python3 --version
```

If that prints `Python 3.10.x` or higher, skip ahead. Otherwise:

- **Mac:** install Homebrew from https://brew.sh, then `brew install python`
- **Windows:** install from https://www.python.org/downloads (check the box
  that says "Add Python to PATH" during the installer)

Install VS Code from https://code.visualstudio.com if you do not already have it.

Then open this project:

```bash
code "enstui-advisor.code-workspace"
```

Or just double-click `enstui-advisor.code-workspace` in Finder / Explorer.

---

## Step 1 — Get the three required keys

Do these in any order. Each gives you a string to paste into `.env`
(which has already been created for you in this folder).

### 1a. Gemini API key  (the AI brain)

1. Go to https://aistudio.google.com/apikey
2. Sign in with your Google account
3. Click **Create API key** → pick any project (or let it create one)
4. Copy the key — it starts with `AIza...`

Paste into `.env` as `GEMINI_API_KEY=...`

No credit card. Free tier gives you 1,500 chat messages/day and
effectively unlimited embeddings for this project.

### 1b. YouTube Data API v3 key  (to scrape the channel)

1. Go to https://console.cloud.google.com
2. Click the project dropdown at the top → **New Project** → name it anything
   (or reuse the project Gemini created in step 1a)
3. Left menu: **APIs & Services → Library**
4. Search for "YouTube Data API v3" → click it → **Enable**
5. Left menu: **APIs & Services → Credentials → + Create Credentials → API Key**
6. Copy the key (also starts with `AIza...`)

Paste into `.env` as `YOUTUBE_API_KEY=...`

### 1c. Supabase URL and service_role key  (the vector database)

1. Go to https://supabase.com → **Start your project** → sign in with GitHub
2. **New Project** → pick any org, name it `enstui-advisor`, set a DB password
   (save the password somewhere, though you will not need it for this app)
3. Wait ~2 minutes for the project to finish setting up
4. Left sidebar: the **gear icon (Project Settings) → API**
5. Copy two things from this page:
   - **Project URL**  →  paste as `SUPABASE_URL=` in `.env`
   - **Project API keys → `service_role` → Reveal → copy**  →  paste as
     `SUPABASE_SERVICE_KEY=` in `.env`

**Important:** use the `service_role` key, NOT the `anon` key. The anon key
does not have write permission.

Then, still in Supabase:

6. Left sidebar: **SQL Editor → New query**
7. Open the file `supabase_setup.sql` from this project in VS Code
8. Copy the entire file contents → paste into the Supabase SQL Editor
9. Click **Run** (bottom right)
10. You should see "Success. No rows returned." — the table, index, and
    search function are now created (using 768-dim vectors for Gemini).

---

## Step 2 — Verify your .env file

Open `.env` in VS Code. Every line that says `PASTE_YOUR_..._HERE` should now
have a real value. The optional keys (GCLOUD, TWILIO, ALERT, SMTP) stay blank.

Save the file.

---

## Step 3 — Run the bootstrap wizard

In the VS Code terminal (open with Ctrl+` or Cmd+`):

```bash
python3 bootstrap.py
```

This one command does everything:

- Creates a Python virtual environment in `.venv`
- Installs all dependencies from `requirements.txt`
- Validates each of your API keys with a real test call
- Checks that the Supabase table exists
- Scrapes the @EnstuiOu channel for transcripts
- Embeds every transcript into Supabase via Gemini
- Launches the Streamlit app

Expect about 5–10 minutes the first time. When it is done, your default
browser will open to http://localhost:8501 with the advisor chat.

If bootstrap fails partway through, run it again — it is idempotent and
picks up where it left off.

---

## Step 4 — Day-to-day use

From now on, one command starts the app:

```bash
python3 run.py
```

Or from the Makefile:

```bash
make run
```

The app opens at http://localhost:8501. `run.py` also self-heals: if the app
crashes it restarts up to 5 times and applies fixes between retries.

### The pages in the browser

- **👑 Advisor Chat** — the main interface. Use the sidebar "Situation / Goal /
  Evidence" form for structured advice, or just type in the chat box.
- **📚 Upload Books** — drag and drop a PDF, it gets chunked and embedded so
  the advisor can cite it.
- **🗄️ Knowledge Base** — see everything indexed, test searches, delete sources.
- **📸 Analyze Conversation** — upload a screenshot of a text exchange and get
  a breakdown of the dynamics (uses Gemini vision).
- **🤖 Autopilot** — generate a timed message sequence (optional Twilio
  integration for auto-sending).

---

## Switching Gemini models

You can switch between fast and smart at any time by editing `.env`:

```env
GEMINI_CHAT_MODEL=gemini-2.5-flash    # fast, free tier friendly (default)
GEMINI_CHAT_MODEL=gemini-2.5-pro      # smarter, tighter free quota
```

Save, restart the app. No code changes needed.

---

## When things break

Run the health check first — it diagnoses every component:

```bash
python3 health.py
```

Common fixes:

| Error | Fix |
|---|---|
| `ModuleNotFoundError` | `pip install -r requirements.txt` inside `.venv` |
| `API_KEY_INVALID` (Gemini) | Re-check `GEMINI_API_KEY` in `.env`, save, retry |
| `API key not valid` (YouTube) | Make sure "YouTube Data API v3" is enabled for that key |
| `relation "enstui_chunks" does not exist` | Re-run `supabase_setup.sql` in Supabase SQL Editor |
| `expected 768 dimensions` | Old 1536-dim schema. Drop the table in Supabase, re-run `supabase_setup.sql`, re-embed |
| `Port 8501 is already in use` | Close old Streamlit tabs, restart the terminal |
| `YouTube quota exceeded` | Resets at midnight Pacific time; try again tomorrow |
| Environment totally broken | `make heal` wipes and rebuilds `.venv` in ~2 min |

---

## Files you will touch regularly

- `.env` — your keys live here; edit if a key changes.
- `books/` — drop PDFs in here and run `make books` to embed them (or use the
  Upload Books page in the browser, which does the same thing).
- `transcripts/` — created automatically by the scraper; you should not need
  to edit these.

Everything else can stay as-is.

---

## One-line summary

```bash
# 1. Fill in .env with GEMINI_API_KEY, YOUTUBE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
# 2. Paste supabase_setup.sql into the Supabase SQL Editor and click Run
# 3. python3 bootstrap.py
# 4. Open http://localhost:8501
```

That is the whole thing. No credit cards anywhere.
