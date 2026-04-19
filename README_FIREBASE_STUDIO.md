# 👑 Enstui Ou — Strategic Advisor
### Firebase Studio / Google Antigravity Workspace

This workspace is fully self-configuring. The environment installs itself,
heals itself when something breaks, and runs the app with a single command.

---

## ⚡ Getting Started (3 Steps Only)

### Step 1 — Add Your API Keys

Open the `.env` file in this editor and fill in the 5 keys:

```env
YOUTUBE_API_KEY       → console.cloud.google.com  → YouTube Data API v3
OPENAI_API_KEY        → platform.openai.com        → API Keys
SUPABASE_URL          → supabase.com               → Project Settings → API
SUPABASE_SERVICE_KEY  → supabase.com               → Project Settings → API
ANTHROPIC_API_KEY     → console.anthropic.com      → API Keys
```

Or run `make open-env` in the terminal to open it directly.

### Step 2 — Set Up Supabase (one-time, 30 seconds)

1. Go to [supabase.com](https://supabase.com) → your project → **SQL Editor**
2. Open `supabase_setup.sql` from this editor
3. Copy all the SQL → paste into Supabase → click **Run**

### Step 3 — Run the Pipeline

Open the Terminal (`Ctrl+J`) and type:

```bash
make pipeline    # Scrapes YouTube + embeds everything into Supabase
make run         # Launches the advisor app
```

**The app preview opens automatically in the right panel.**

---

## 🤖 Self-Healing System

If anything ever breaks — wrong Python version, missing package, crashed script —
the system fixes itself automatically. You can also force it:

```bash
make heal        # Wipes and reinstalls the entire environment
make check       # Runs health check and auto-fixes any issues
make status      # Shows what's installed, what's indexed, last run time
```

The system checks its own health every time the workspace opens.

---

## 📋 All Commands

| Command | What it does |
|---------|-------------|
| `make setup` | First-time install (runs automatically on first open) |
| `make run` | Launch the Streamlit chat app |
| `make scrape` | Pull latest videos from @EnstuiOu YouTube channel |
| `make embed` | Embed transcripts into Supabase vector database |
| `make books` | Embed PDFs from the `books/` folder |
| `make pipeline` | Run scrape + embed in one shot |
| `make heal` | Force full environment reset |
| `make check` | Health check + auto-fix |
| `make status` | System status dashboard |

---

## 📁 Project Structure

```
.idx/
  dev.nix                   ← Firebase Studio environment config (this controls everything)

App Pages:
  app.py                    ← 👑 Main advisor chat
  pages/1_📚_Upload_Books.py ← 📚 PDF upload page
  pages/2_🗄️_Knowledge_Base.py ← 🗄️ Knowledge base manager

Pipeline:
  scraper.py                ← Step 1: YouTube scraper
  embed_transcripts.py      ← Step 2a: Embed video transcripts
  embed_books.py            ← Step 2b: Embed PDF books
  whisper_fallback.py       ← Whisper transcription for no-caption videos

Core Modules:
  advisor.py                ← Claude API + RAG brain
  retriever.py              ← Supabase vector search
  kb_manager.py             ← Knowledge base management backend

Orchestration:
  setup_and_run.py          ← Master orchestrator (setup, health, healing)
  Makefile                  ← Single-word commands

Database:
  supabase_setup.sql        ← Run once in Supabase SQL Editor

Config:
  .env                      ← Your API keys (never commit this)
  .env.example              ← Template for .env
  requirements.txt          ← Python dependencies

Data:
  transcripts/              ← Downloaded video transcripts (JSON)
  books/                    ← Drop PDF books here
```

---

## 🔑 Where to Get Each API Key

| Key | Where | Free? |
|-----|-------|-------|
| `YOUTUBE_API_KEY` | [console.cloud.google.com](https://console.cloud.google.com) → Enable YouTube Data API v3 → Credentials | ✅ Free |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | 💳 ~$0.05 total to embed full channel |
| `SUPABASE_URL` | [supabase.com](https://supabase.com) → New Project → Settings → API | ✅ Free tier |
| `SUPABASE_SERVICE_KEY` | Same place, use the `service_role` key | ✅ Free tier |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | 💳 Pay per message |

---

## ❓ Troubleshooting

**App won't start:**
```bash
make heal && make run
```

**Transcripts not appearing:**
```bash
make scrape
make status   # shows how many were downloaded
```

**Books not being found:**
- Drop PDFs into the `books/` folder
- Run `make books`
- Check the Knowledge Base page in the app

**Supabase errors:**
- Make sure you ran `supabase_setup.sql` in Supabase SQL Editor
- Check that `SUPABASE_SERVICE_KEY` is the `service_role` key, not `anon`

**Environment completely broken:**
```bash
make heal
```
This wipes the virtual environment and rebuilds from scratch in ~2 minutes.
