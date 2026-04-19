"""
pages/2_🗄️_Knowledge_Base.py

Knowledge Base Manager — full visibility and control over
every video and book in the Supabase vector database.

Features:
  - Live stats dashboard
  - Searchable source table
  - Delete individual sources
  - Nuke all books at once
  - Preview chunk content for any source
"""

import streamlit as st

# Secrets bridge + password gate (must run before importing kb_manager/retriever)
from streamlit_cloud import load_secrets, require_password
load_secrets()
require_password()

from kb_manager import (
    get_supabase,
    get_kb_summary,
    delete_source,
    delete_all_books,
    list_all_sources,
)
from retriever import search, get_clients as get_rag_clients

# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title = "Knowledge Base — Enstui Ou",
    page_icon  = "🗄️",
    layout     = "wide"
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); color: #f0f0f0; }
    [data-testid="stSidebar"] { background: #111 !important; border-right: 1px solid #222; }
    hr { border-color: #333 !important; }

    .page-header {
        text-align: center; padding: 1.5rem 0;
        border-bottom: 1px solid #333; margin-bottom: 2rem;
    }
    .page-header h1 { color: #d4af37; font-size: 1.8rem; margin: 0; }
    .page-header p  { color: #888; font-size: 0.9rem; margin-top: 0.4rem; }

    .stat-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }
    .stat-number { font-size: 2.2rem; font-weight: 700; color: #d4af37; line-height: 1; }
    .stat-label  { color: #888; font-size: 0.85rem; margin-top: 0.3rem; }

    .source-row {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .source-type-video { border-left: 3px solid #4a90d9; }
    .source-type-book  { border-left: 3px solid #d4af37; }

    .chunk-preview {
        background: rgba(0,0,0,0.4);
        border: 1px solid #333;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.82rem;
        color: #aaa;
        font-family: monospace;
        margin-top: 0.5rem;
        max-height: 200px;
        overflow-y: auto;
    }

    .stButton > button {
        background: linear-gradient(135deg, #d4af37, #b8943f);
        color: #000; font-weight: 700; border: none; border-radius: 8px;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #e8c84b, #d4af37); }

    .danger-btn > button {
        background: rgba(239,68,68,0.8) !important;
        color: #fff !important;
    }
    .danger-btn > button:hover { background: rgba(239,68,68,1) !important; }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="page-header">
    <h1>🗄️ Knowledge Base Manager</h1>
    <p>View, search, and manage every video and book indexed in your advisor's brain.</p>
</div>
""", unsafe_allow_html=True)


# ── Init ──────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    return get_supabase()

try:
    supabase = get_db()
except EnvironmentError as e:
    st.error(f"⚠️ {e}")
    st.stop()


# ── Stats Dashboard ───────────────────────────────────────────────────────────

summary = get_kb_summary(supabase)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{summary['video_count']}</div>
        <div class="stat-label">📺 Videos</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{summary['book_count']}</div>
        <div class="stat-label">📗 Books</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{summary['total_chunks']:,}</div>
        <div class="stat-label">🧩 Total Chunks</div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{summary['total_sources']}</div>
        <div class="stat-label">📦 Total Sources</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ── Search Test ───────────────────────────────────────────────────────────────

with st.expander("🔍 Test a Search Query", expanded=False):
    st.markdown("Enter any query to see exactly what the advisor would retrieve.")

    q_col, f_col = st.columns([3, 1])
    with q_col:
        test_query = st.text_input("Query", placeholder="e.g. Teknik Zonbifye", label_visibility="collapsed")
    with f_col:
        filter_opt = st.selectbox("Filter", ["All", "Videos only", "Books only"], label_visibility="collapsed")

    if st.button("🔍 Search") and test_query:
        source_filter = None
        if filter_opt == "Videos only":
            source_filter = "video"
        elif filter_opt == "Books only":
            source_filter = "book"

        with st.spinner("Searching..."):
            try:
                ai_client, sb = get_rag_clients()
                results = search(
                    test_query,
                    match_count     = 6,
                    match_threshold = 0.35,
                    source_filter   = source_filter,
                    ai_client       = ai_client,
                    supabase        = sb
                )
            except Exception as e:
                st.error(f"Search failed: {e}")
                results = []

        if not results:
            st.warning("No results found. Try a different query or lower the threshold.")
        else:
            st.success(f"Found {len(results)} relevant chunks:")
            for r in results:
                icon = "📺" if r["source_type"] == "video" else "📗"
                with st.container():
                    st.markdown(
                        f"**{icon} {r['title']}** — similarity: `{r['similarity']:.3f}`"
                    )
                    st.markdown(
                        f'<div class="chunk-preview">{r["chunk_text"][:600]}</div>',
                        unsafe_allow_html=True
                    )


st.divider()


# ── Source Browser ────────────────────────────────────────────────────────────

st.markdown("#### 📋 All Sources")

# Filter controls
filter_col, search_col = st.columns([1, 3])

with filter_col:
    type_filter = st.selectbox(
        "Type",
        ["All", "Videos", "Books"],
        label_visibility="collapsed"
    )

with search_col:
    title_search = st.text_input(
        "Search titles",
        placeholder="Filter by title...",
        label_visibility="collapsed"
    )

# Apply filters
sources = summary["sources"]

if type_filter == "Videos":
    sources = [s for s in sources if s["source_type"] == "video"]
elif type_filter == "Books":
    sources = [s for s in sources if s["source_type"] == "book"]

if title_search:
    sources = [s for s in sources if title_search.lower() in s["title"].lower()]

st.caption(f"Showing {len(sources)} of {summary['total_sources']} sources")
st.markdown("")

if not sources:
    st.info("No sources match the current filter.")
else:
    for source in sources:
        s_type   = source["source_type"]
        icon     = "📺" if s_type == "video" else "📗"
        color    = "#4a90d9" if s_type == "video" else "#d4af37"
        chunks   = source.get("chunk_count", 0)
        embedded = source.get("embedded_at", "")[:10]

        col_info, col_action = st.columns([5, 1])

        with col_info:
            with st.expander(f"{icon}  {source['title']}  —  {chunks} chunks  ·  {embedded}"):
                st.markdown(f"**Source ID:** `{source['source_id']}`")
                st.markdown(f"**Type:** {s_type.title()}")
                st.markdown(f"**Chunks:** {chunks}")
                st.markdown(f"**Indexed:** {embedded}")

                if s_type == "video":
                    # Try to fetch a sample chunk to preview
                    try:
                        sample = supabase.table("enstui_chunks") \
                            .select("chunk_text") \
                            .eq("video_id", source["source_id"]) \
                            .limit(1) \
                            .execute()
                        if sample.data:
                            st.markdown("**Sample chunk:**")
                            st.markdown(
                                f'<div class="chunk-preview">{sample.data[0]["chunk_text"][:400]}</div>',
                                unsafe_allow_html=True
                            )
                    except Exception:
                        pass

        with col_action:
            if st.button("🗑️ Delete", key=f"del_{source['source_id']}"):
                st.session_state[f"confirm_{source['source_id']}"] = True

            # Confirmation dialog
            if st.session_state.get(f"confirm_{source['source_id']}"):
                st.warning(f"Delete **{source['title']}**?")
                ccol1, ccol2 = st.columns(2)
                with ccol1:
                    if st.button("✅ Yes", key=f"yes_{source['source_id']}"):
                        with st.spinner("Deleting..."):
                            result = delete_source(supabase, source["source_id"], source["title"])
                        if result["success"]:
                            st.success(f"Deleted: {source['title']}")
                        else:
                            st.error(f"Failed: {result.get('error')}")
                        del st.session_state[f"confirm_{source['source_id']}"]
                        st.rerun()
                with ccol2:
                    if st.button("❌ No", key=f"no_{source['source_id']}"):
                        del st.session_state[f"confirm_{source['source_id']}"]
                        st.rerun()


st.divider()


# ── Danger Zone ───────────────────────────────────────────────────────────────

with st.expander("⚠️ Danger Zone", expanded=False):
    st.markdown("These actions are permanent and cannot be undone.")

    if summary["book_count"] > 0:
        st.markdown(f"**Delete all {summary['book_count']} books** from the knowledge base.")
        if st.button("🗑️ Delete All Books"):
            st.session_state["confirm_all_books"] = True

        if st.session_state.get("confirm_all_books"):
            st.warning(f"This will permanently remove all {summary['book_count']} books and their chunks. Sure?")
            da_col1, da_col2 = st.columns(2)
            with da_col1:
                if st.button("✅ Yes, delete all books"):
                    with st.spinner("Deleting all books..."):
                        result = delete_all_books(supabase)
                    if result["success"]:
                        st.success(f"Deleted {result['deleted']} books.")
                    else:
                        st.error(f"Partial failure: {result.get('errors')}")
                    del st.session_state["confirm_all_books"]
                    st.rerun()
            with da_col2:
                if st.button("❌ Cancel"):
                    del st.session_state["confirm_all_books"]
                    st.rerun()
    else:
        st.info("No books to delete.")
