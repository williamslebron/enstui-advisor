# Deploy to Streamlit Community Cloud

Put your Enstui Ou advisor online at a permanent URL like
`https://enstui-will.streamlit.app`. Free. Always on. Your Mac can be off.

Total time: ~15 minutes.

---

## What you'll end up with

- A **private GitHub repo** holding your code (no secrets).
- A **Streamlit Cloud deployment** running `app.py` with your 4 API keys stored
  securely in Streamlit's secrets UI.
- A **password-gated** app — anyone with the URL still needs your password to use it.
- A **nightly GitHub Action** that scrapes new videos and embeds them. You don't
  have to do anything after the initial setup; the app updates itself.

---

## Step 1 — Create a private GitHub repo

1. Go to https://github.com/new
2. **Repository name:** `enstui-advisor` (or anything you want)
3. **Visibility:** Private
4. Leave everything else blank — do NOT initialize with README or .gitignore
5. Click **Create repository**

GitHub will show a page with instructions. Ignore them — use the ones below instead.

---

## Step 2 — Push your code to the repo

In the VS Code terminal, from inside the project folder:

```bash
# Make sure you're in the project folder
cd "/Users/willdodo/Downloads/enstui_scraper 2"

# First time only — initialize git
git init
git branch -M main

# Stage everything (.env is already excluded by .gitignore)
git add .

# Sanity check — .env should NOT appear here
git status | grep -E '\.env$|secrets\.toml$'

# Commit
git commit -m "Initial commit — Enstui Ou advisor (Gemini edition)"

# Connect to the GitHub repo you just made (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/enstui-advisor.git

# Push
git push -u origin main
```

If the last command asks for credentials:
- **Username:** your GitHub username
- **Password:** NOT your GitHub password. You need a Personal Access Token.
  Go to https://github.com/settings/tokens → **Generate new token (classic)** →
  check the `repo` scope → generate → copy the token → paste it as the password.

If the `git status | grep` command printed a line with `.env` in it, STOP.
That means `.env` is about to be committed. Don't push. Check `.gitignore`
is correct, run `git rm --cached .env`, then re-commit.

---

## Step 3 — Sign up for Streamlit Community Cloud

1. Go to https://streamlit.io/cloud
2. Click **Sign in with GitHub**
3. Authorize Streamlit to access your repos (read-only is fine — it just lists them)

---

## Step 4 — Deploy the app

1. On the Streamlit Cloud dashboard, click **Create app** → **Deploy a public app from GitHub**
2. Fill in:
   - **Repository:** `YOUR_USERNAME/enstui-advisor`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** pick a subdomain, e.g. `enstui-will` → becomes `https://enstui-will.streamlit.app`
3. Click **Advanced settings**
   - **Python version:** 3.11
   - **Secrets:** paste the block below (replace each value with your real key),
     then click Save.

Paste this into the Secrets box, with your real keys:

```toml
YOUTUBE_API_KEY       = "AIza..."
SUPABASE_URL          = "https://your-project-id.supabase.co"
SUPABASE_SERVICE_KEY  = "eyJ..."
GEMINI_API_KEY        = "AIza..."

GEMINI_CHAT_MODEL  = "gemini-2.5-flash"
GEMINI_EMBED_MODEL = "text-embedding-004"

APP_PASSWORD = "pick-a-strong-password"
```

Tip: your existing `.env` file has the four real keys — just copy them out.
Note the format changes — `.env` uses `KEY=value`, Streamlit secrets uses
`KEY = "value"` (with quotes and spaces).

4. Click **Deploy**.

Streamlit will take ~2 minutes to install your requirements and boot the app.
When it finishes, your URL becomes live. Visit it — you should see the
password prompt. Enter the password you set in `APP_PASSWORD`. You're in.

---

## Step 5 — (Recommended) Set up the nightly auto-update

The project already has a `.github/workflows/daily_scraper.yml` workflow that
scrapes new videos every day at 8 AM UTC and embeds them into Supabase.
Streamlit Cloud will then pick up the new data automatically. To enable it:

1. On GitHub, go to **your repo** → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**, add each one:
   - `YOUTUBE_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `GEMINI_API_KEY`
3. Go to the **Actions** tab. GitHub may have disabled the workflow by default —
   click it and enable it if needed.
4. Click **Run workflow** once manually to confirm it works.

From now on, the workflow runs every night. No action needed from you.

---

## How to update the live app

Anything you change locally — just push it:

```bash
git add .
git commit -m "Describe what you changed"
git push
```

Streamlit Cloud watches your repo and redeploys within ~1 minute of every push.

---

## Changing the password

**Streamlit Cloud** side:
1. Streamlit Cloud dashboard → your app → ⋯ → **Settings** → **Secrets**
2. Edit the `APP_PASSWORD` value, click **Save**
3. The app reboots in a few seconds with the new password

**Locally** (so running `python run.py` on your Mac also requires the password):
1. Open `.env` → set `APP_PASSWORD=your-password` → save
2. Restart `python run.py`

Leave `APP_PASSWORD=` blank locally if you want no password when developing.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Deploy fails at "Installing dependencies" | Check the Streamlit Cloud logs — usually one package name is wrong. Compare against `requirements.txt`. |
| App loads but says "Missing GEMINI_API_KEY" | You didn't save the secrets. Settings → Secrets → paste again → Save. |
| Password prompt doesn't appear | `APP_PASSWORD` is blank in Streamlit secrets. Set it. |
| Nightly workflow fails with "Permission denied" | The workflow needs `contents: write`. Already set — re-check `.github/workflows/daily_scraper.yml`. Also confirm **Settings → Actions → General → Workflow permissions → Read and write** on your repo. |
| App is slow on first visit | Streamlit Cloud puts free apps to sleep after inactivity. First visit wakes them — takes ~30 seconds, then it's fast. |
| Free quota exhausted | Gemini free tier resets daily. Either wait or put up a stricter password. |

---

## Security reminders

- Your `.env` is NOT in the GitHub repo (verified by `.gitignore`). Good.
- Your **Supabase service_role key** gives full database access. Never paste it
  anywhere public. If it leaks, rotate it in Supabase → Project Settings → API.
- Your **Gemini key** can be rate-limited but in the free tier it's hard to rack
  up real money. Still, don't share it.
- The password gate is a soft lock — it prevents casual strangers, not a
  determined attacker. For anything high-stakes, use Streamlit's built-in
  authentication (paid).
