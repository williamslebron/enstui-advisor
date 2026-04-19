# Step 4 — Book Upload UI & Knowledge Base Manager

The app is now a full multi-page system. No more terminal commands needed
for managing books — everything is done through the browser.

---

## New Pages

```
app.py                          →  👑 Advisor Chat      (same as Step 3)
pages/1_📚_Upload_Books.py      →  📚 Upload Books      (NEW)
pages/2_🗄️_Knowledge_Base.py   →  🗄️ Knowledge Base    (NEW)
```

Navigate between them using the sidebar links.

---

## 📚 Upload Books Page

Drag and drop any PDF directly in the browser.

What happens:
1. PDF is read in-memory (never touches disk)
2. All pages extracted into text
3. Split into 400-token overlapping chunks
4. Each chunk embedded via OpenAI
5. Stored in Supabase alongside video data
6. Advisor can now reference it immediately

You can optionally set a custom title — this is what appears in
the advisor's citations when it references the book.

**Duplicate protection:** If you upload the same file twice,
it detects it and skips re-embedding.

---

## 🗄️ Knowledge Base Page

Full visibility and control over everything indexed.

Features:
- **Stats dashboard** — video count, book count, total chunks at a glance
- **Search tester** — type any query and see exactly what chunks the advisor would retrieve, with similarity scores
- **Source browser** — filterable, searchable table of every video and book
- **Chunk preview** — click any source to see a sample of its stored content
- **Delete individual sources** — with a confirmation step so you can't accidentally nuke anything
- **Delete all books** — in the Danger Zone section, with double-confirmation

---

## New File: kb_manager.py

Backend module that powers both new pages:
- `list_all_sources()` — full source listing from Supabase
- `get_kb_summary()` — stats for the dashboard
- `delete_source()` — removes all chunks + tracking record for one source
- `delete_all_books()` — bulk book removal
- `embed_and_store_book()` — the full upload pipeline from browser bytes to Supabase

---

## Full System Architecture (All 4 Steps)

```
┌─────────────────────────────────────────────────────────┐
│                    DAILY (GitHub Actions)                │
│  scraper.py → transcripts/*.json → embed_transcripts.py │
│                          ↓                               │
│                   Supabase pgvector                      │
└─────────────────────────────────────────────────────────┘
                           ↑
              embed_books.py (from browser upload)

┌─────────────────────────────────────────────────────────┐
│                    STREAMLIT APP                         │
│                                                         │
│  app.py           👑 Advisor Chat                       │
│  ├── advisor.py      ← Claude API + RAG                  │
│  └── retriever.py    ← Supabase search                   │
│                                                         │
│  pages/1_Upload_Books.py   📚 Browser PDF upload         │
│  └── kb_manager.py         ← embed_and_store_book()      │
│                                                         │
│  pages/2_Knowledge_Base.py 🗄️ Source manager             │
│  └── kb_manager.py         ← list, delete, preview       │
└─────────────────────────────────────────────────────────┘
```

---

## Running It

Nothing changes from Step 3:

```bash
streamlit run app.py
```

The new pages appear automatically in the sidebar navigation.
