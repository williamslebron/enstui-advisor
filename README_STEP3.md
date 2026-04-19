# Step 3 — The AI Advisor

This step wires everything together: Claude API + RAG retrieval = a
live, context-aware Enstui Ou Strategic Advisor with a full chat UI.

---

## How It Works

```
User types a message
        │
        ▼
advisor.py builds a search query
        │
        ▼
retriever.py embeds it → searches Supabase (pgvector)
        │
        ▼
Top 8 most relevant chunks returned
(from videos + books combined)
        │
        ▼
Chunks injected into Claude's system prompt
        │
        ▼
Claude responds as the Enstui Ou advisor
using real channel knowledge as context
        │
        ▼
Response shown in Streamlit chat UI
```

Every single message gets a fresh RAG lookup.
The AI always answers from the channel's real content, not just training data.

---

## Setup

### 1. Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com) → API Keys
2. Create a new key
3. Add to `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Make sure Step 2 is done

The advisor needs data in Supabase to retrieve from.
If you haven't run Step 2 yet:
```bash
python embed_transcripts.py   # Videos
python embed_books.py         # Books (optional)
```

### 3. Install new dependencies

```bash
pip install -r requirements.txt
```

### 4. Launch the chat UI

```bash
streamlit run app.py
```

Opens at: http://localhost:8501

---

## Using the Advisor

### Option A — Quick Sidebar Form
Fill in the three fields on the left:
- **Situation** — what just happened
- **Goal** — what you want next
- **Evidence** — paste the last text received

Click **Analyze My Situation** → get structured advice instantly.

### Option B — Free Chat
Type anything in the chat box at the bottom.
Works for follow-up questions, technique explanations, or asking about
specific videos.

---

## Terminal Mode (no UI)

If you just want to test without Streamlit:

```bash
python advisor.py
```

---

## File Summary

| File | Purpose |
|------|---------|
| `advisor.py` | Core advisor — Claude API + RAG, stateful chat |
| `app.py` | Streamlit web UI with sidebar situation form |
| `retriever.py` | Supabase vector search (from Step 2) |

---

## Deploying Online (Optional)

To share the advisor with others or access it from your phone:

### Streamlit Community Cloud (Free)
1. Push your repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo → set `app.py` as the entry point
4. Add secrets (API keys) in the Streamlit dashboard
5. Your advisor is live at a public URL

### Railway / Render
Both support one-click Python app deployment with environment variables.
Use `streamlit run app.py --server.port $PORT` as the start command.

---

## Next Step

**Step 4** adds:
- File upload UI so you can drop in new books directly from the browser
- Knowledge base management (see what's indexed, delete sources)
- Multi-user session support
