# Step 2 — Embedding & Vector Database

This step takes every transcript JSON from Step 1, breaks it into chunks,
creates semantic embeddings via OpenAI, and stores everything in Supabase
so the AI advisor can search it in milliseconds.

---

## Architecture

```
transcripts/*.json   ──► chunk_text()  ──► OpenAI embed  ──► Supabase pgvector
books/*.pdf          ──► extract_pdf() ──► OpenAI embed  ──► Supabase pgvector
                                                               │
                                               retriever.py ◄─┘
                                               (used by Step 3 AI advisor)
```

---

## One-Time Setup

### 1. Create a Free Supabase Project

1. Go to [supabase.com](https://supabase.com) → New Project
2. Choose a name (e.g. `enstui-advisor`) and a strong DB password
3. Wait ~2 minutes for it to spin up
4. Go to **Project Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role key** → `SUPABASE_SERVICE_KEY`  *(not the anon key)*

### 2. Run the SQL Setup Script

1. In your Supabase dashboard → **SQL Editor → New Query**
2. Paste the entire contents of `supabase_setup.sql`
3. Click **Run**

This creates the `enstui_chunks` table, vector index, and search function.

### 3. Get an OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com) → API Keys
2. Create a new key → copy it to `.env` as `OPENAI_API_KEY`

**Cost estimate:** ~$0.002 per 1,000 chunks with `text-embedding-3-small`.
A channel with 100 videos ≈ roughly 500–2,000 chunks ≈ **under $0.05 total**.

### 4. Update Your .env

```env
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
```

---

## Running It

### Embed all video transcripts:
```bash
python embed_transcripts.py
```

### Embed books (optional):
```bash
# Drop PDF files into the /books folder first
mkdir books
# Copy your PDFs there, then:
python embed_books.py
```

### Test the search:
```bash
# Search for a specific technique
python retriever.py "Teknik Zonbifye"

# Search in Haitian Creole
python retriever.py "kijan pouw jere yon fi ki fret"

# Search only books
python retriever.py "Belle Mots technique"
```

---

## What Gets Stored

Every chunk in Supabase contains:

| Column | Description |
|--------|-------------|
| `video_id` | YouTube ID or book hash |
| `title` | Video title or book name |
| `url` | YouTube URL (null for books) |
| `source_type` | `"video"` or `"book"` |
| `chunk_index` | Position within the source |
| `chunk_text` | The actual text (400 tokens) |
| `embedding` | 1536-float vector |

---

## Daily Automation

The updated `.github/workflows/daily_scraper.yml` now runs both steps:
1. Scrape new videos (Step 1)
2. Embed new transcripts (Step 2)

Add these GitHub Secrets:
- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

---

## Next Step

Once embedding is done, run:
```bash
python retriever.py "your question here"
```

If you see relevant chunks returned, you're ready for **Step 3** — connecting
the AI advisor that uses these chunks as live context.
