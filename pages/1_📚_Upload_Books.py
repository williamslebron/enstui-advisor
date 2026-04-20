"""
pages/1_📚_Upload_Books.py

Streamlit page for uploading PDF books directly from the browser.
Drop a PDF → it gets extracted, chunked, embedded, and added to the
knowledge base in real time — no terminal needed.
"""

import streamlit as st

# ── Page Config — MUST be the first Streamlit call ────────────────────────────
st.set_page_config(
    page_title = "Upload Books — Enstui Ou",
    page_icon  = "📚",
    layout     = "centered"
)

# Secrets bridge + password gate (must run before importing kb_manager)
from streamlit_cloud import load_secrets, require_password
load_secrets()
require_password()

from kb_manager import (
    get_supabase,
    get_ai_client,
    embed_and_store_book,
    list_all_sources,
)

# ── CSS (matches main app theme) ──────────────────────────────────────────────

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); color: #f0f0f0; }
    [data-testid="stSidebar"] { background: #111 !important; border-right: 1px solid #222; }
    hr { border-color: #333 !important; }

    .page-header {
        text-align: center;
        padding: 1.5rem 0;
        border-bottom: 1px solid #333;
        margin-bottom: 2rem;
    }
    .page-header h1 { color: #d4af37; font-size: 1.8rem; margin: 0; }
    .page-header p  { color: #888; font-size: 0.9rem; margin-top: 0.4rem; }

    .upload-zone {
        border: 2px dashed #444;
        border-radius: 16px;
        padding: 2.5rem;
        text-align: center;
        background: rgba(255,255,255,0.02);
        margin-bottom: 1.5rem;
        transition: border-color 0.2s;
    }
    .upload-zone:hover { border-color: #d4af37; }

    .result-card {
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }
    .result-success { background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); }
    .result-error   { background: rgba(239,68,68,0.12);  border: 1px solid rgba(239,68,68,0.3); }
    .result-warning { background: rgba(234,179,8,0.12);  border: 1px solid rgba(234,179,8,0.3); }

    .book-badge {
        display: inline-block;
        background: rgba(212,175,55,0.15);
        border: 1px solid rgba(212,175,55,0.4);
        border-radius: 20px;
        padding: 0.2rem 0.75rem;
        font-size: 0.8rem;
        color: #d4af37;
        margin: 0.2rem;
    }

    .stButton > button {
        background: linear-gradient(135deg, #d4af37, #b8943f);
        color: #000; font-weight: 700; border: none;
        border-radius: 8px; width: 100%;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #e8c84b, #d4af37); }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="page-header">
    <h1>📚 Upload Books</h1>
    <p>Add the author's books to the knowledge base. The advisor will reference them instantly.</p>
</div>
""", unsafe_allow_html=True)


# ── Init clients ──────────────────────────────────────────────────────────────

@st.cache_resource
def get_clients():
    return get_supabase(), get_ai_client()

try:
    supabase, ai_client = get_clients()
except EnvironmentError as e:
    st.error(f"⚠️ Configuration error: {e}")
    st.stop()


# ── Currently Indexed Books ───────────────────────────────────────────────────

sources = list_all_sources(supabase)
books   = [s for s in sources if s["source_type"] == "book"]

if books:
    st.markdown("#### 📖 Currently in Knowledge Base")
    book_html = "".join(
        f'<span class="book-badge">📗 {b["title"]} ({b.get("chunk_count",0)} chunks)</span>'
        for b in books
    )
    st.markdown(book_html, unsafe_allow_html=True)
    st.markdown("")
else:
    st.info("No books indexed yet. Upload your first PDF below.")


st.divider()


# ── Upload Form ───────────────────────────────────────────────────────────────

st.markdown("#### ⬆️ Upload a New Book")
st.markdown("Accepts any PDF with selectable text. Scanned PDFs need OCR first.")

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader(
        "Drop PDF here or click to browse",
        type        = ["pdf"],
        label_visibility = "collapsed"
    )

with col2:
    custom_title = st.text_input(
        "Custom title (optional)",
        placeholder = "e.g. The King's Code",
        help        = "Leave blank to use the filename as the title."
    )

if uploaded_file is not None:
    file_size_mb = uploaded_file.size / (1024 * 1024)

    st.markdown(f"""
    <div class="upload-zone">
        <p style="color:#d4af37; font-size:1.1rem; margin:0;">📄 {uploaded_file.name}</p>
        <p style="color:#888; margin:0.3rem 0 0 0;">{file_size_mb:.1f} MB</p>
    </div>
    """, unsafe_allow_html=True)

    if file_size_mb > 50:
        st.warning("⚠️ Large file detected. Processing may take a few minutes.")

    process_btn = st.button("⚡ Process & Add to Knowledge Base")

    if process_btn:
        pdf_bytes = uploaded_file.read()
        title     = custom_title.strip() if custom_title.strip() else None

        with st.spinner(f"Processing **{uploaded_file.name}** — extracting, chunking, embedding..."):
            result = embed_and_store_book(
                supabase     = supabase,
                ai_client    = ai_client,
                pdf_bytes    = pdf_bytes,
                filename     = uploaded_file.name,
                custom_title = title,
            )

        if result.get("already_exists"):
            st.markdown(f"""
            <div class="result-card result-warning">
                ⚠️ <strong>{result['title']}</strong> is already in the knowledge base.
                Delete it first if you want to re-process it.
            </div>""", unsafe_allow_html=True)

        elif result.get("success"):
            st.markdown(f"""
            <div class="result-card result-success">
                ✅ <strong>{result['title']}</strong> successfully added!<br>
                <span style="color:#888;">{result['chunks']} chunks embedded and indexed.</span>
            </div>""", unsafe_allow_html=True)
            st.balloons()
            # Force a rerun to refresh the "currently indexed" section
            st.rerun()

        else:
            st.markdown(f"""
            <div class="result-card result-error">
                ❌ Failed to process book.<br>
                <span style="color:#f87171;">{result.get('error', 'Unknown error')}</span>
            </div>""", unsafe_allow_html=True)


st.divider()


# ── Batch Upload Info ─────────────────────────────────────────────────────────

with st.expander("💡 Tips for best results"):
    st.markdown("""
**For the best transcript quality:**
- PDF must have **selectable text** (not a scanned image). Open it in a PDF reader and try to highlight text — if you can, it'll work.
- If it's scanned, run it through **Adobe Acrobat → OCR** or **smallpdf.com** first.
- Larger books (200+ pages) will take 1–3 minutes to process.
- The title shown in the advisor's citations comes from your custom title or the filename.

**Adding multiple books:**
You can upload them one at a time. Each one gets added independently.
To replace a book, delete it first from the Knowledge Base page, then re-upload.

**Cost:**
Free. Embeddings run on Gemini's `text-embedding-004` model, which has a generous free tier.
""")
