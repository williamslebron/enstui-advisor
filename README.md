# 👑 Enstui Ou — Strategic Advisor (Gemini Edition)

A live AI advisor powered by the real content of the @EnstuiOu YouTube channel
and any books by the author — fully automated, self-updating, self-healing.
Runs entirely on Google Gemini, with no paid API keys required.

See [**GET_STARTED.md**](GET_STARTED.md) for the full step-by-step walkthrough.

---

## ⚡ How to Start (3 Steps Total)

### Step 1 — Open in VS Code
Double-click `enstui-advisor.code-workspace` to open the project.

### Step 2 — Fill in Your API Keys
Open `.env` and replace all `PASTE_YOUR_..._HERE` placeholders:

| Key | Where to get it | Cost |
|-----|-----------------|------|
| GEMINI_API_KEY       | https://aistudio.google.com/apikey            | Free |
| YOUTUBE_API_KEY      | https://console.cloud.google.com → YouTube Data API v3 | Free |
| SUPABASE_URL         | https://app.supabase.com → Project Settings → API | Free |
| SUPABASE_SERVICE_KEY | same page, use the `service_role` key         | Free |

### Step 3 — Run Setup
Press **Ctrl+Shift+B** (or in the terminal: `python bootstrap.py`)

The wizard does everything: installs packages, validates keys, scrapes the
channel, embeds content with Gemini, and launches the app at
http://localhost:8501.

---

## 🗂 Daily Use (After First Setup)

| Action | How |
|--------|-----|
| Start the app | F5 → "▶️ Run App" or `python run.py` |
| Health check | `python health.py` |
| Add a book | Browser → Upload Books page |
| Manage content | Browser → Knowledge Base page |

---

## 🩺 When Something Goes Wrong

Run `python health.py` — it diagnoses every component and tells you exactly what to fix.

`run.py` auto-restarts the app up to 5 times and applies fixes between retries.

| Error | Fix |
|-------|-----|
| "API_KEY_INVALID" (Gemini) | Check `GEMINI_API_KEY` in `.env` |
| "API key not valid" (YouTube) | Enable "YouTube Data API v3" for that key |
| "relation does not exist" | Run `supabase_setup.sql` in Supabase SQL Editor |
| "expected 768 dimensions" | Old schema — drop `enstui_chunks` and re-run the SQL |
| "Module not found" | `pip install -r requirements.txt` |
| "Port 8501 in use" | Restart VS Code terminal |
| YouTube quota exceeded | Resets at midnight Pacific time |

---

## 📁 Key Files

```
enstui-advisor.code-workspace  ← Open this in VS Code
bootstrap.py                   ← First-time setup (run once)
run.py                         ← Daily launcher + self-healing watchdog
health.py                      ← System diagnostics + auto-repair
app.py                         ← Main chat UI
advisor.py                     ← Gemini chat + RAG brain
gemini_client.py               ← Shared Gemini client helper
```

---

## 🔀 Switching Gemini models

Edit `.env` and restart the app:

```env
GEMINI_CHAT_MODEL=gemini-2.5-flash    # fast, generous free tier (default)
GEMINI_CHAT_MODEL=gemini-2.5-pro      # smartest, tighter quota
```
# enstui-advisor
