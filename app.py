"""
app.py

Step 3 — Streamlit Chat Interface.
Run with:
    streamlit run app.py

Requirements:
    pip install streamlit google-genai
"""

import logging
import streamlit as st

# ── Page Config — MUST be the first Streamlit call ────────────────────────────
st.set_page_config(
    page_title = "Enstui Ou — Strategic Advisor",
    page_icon  = "👑",
    layout     = "centered",
    initial_sidebar_state = "expanded"
)

# ── Streamlit Cloud / local secrets bridge + password gate ───────────────────
# Must run BEFORE importing advisor (which reads GEMINI_API_KEY from env).
from streamlit_cloud import load_secrets, require_password
load_secrets()
require_password()

from advisor import EnstuiAdvisor

logging.basicConfig(level=logging.INFO)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Dark premium background */
    .stApp {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
        color: #f0f0f0;
    }

    /* Header */
    .advisor-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
        border-bottom: 1px solid #333;
        margin-bottom: 1.5rem;
    }
    .advisor-header h1 {
        font-size: 2rem;
        font-weight: 700;
        color: #d4af37;
        letter-spacing: 0.05em;
        margin: 0;
    }
    .advisor-header p {
        color: #888;
        font-size: 0.9rem;
        margin-top: 0.4rem;
    }

    /* Chat messages */
    .stChatMessage {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 12px !important;
        margin-bottom: 0.75rem !important;
    }

    /* User message accent */
    .stChatMessage[data-testid="user-message"] {
        border-left: 3px solid #d4af37 !important;
    }

    /* Advisor message accent */
    .stChatMessage[data-testid="assistant-message"] {
        border-left: 3px solid #4a90d9 !important;
    }

    /* Input box */
    .stChatInput textarea {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid #333 !important;
        color: #f0f0f0 !important;
        border-radius: 12px !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #111 !important;
        border-right: 1px solid #222;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #d4af37, #b8943f);
        color: #000;
        font-weight: 700;
        border: none;
        border-radius: 8px;
        width: 100%;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #e8c84b, #d4af37);
    }

    /* Input labels */
    .situation-label {
        color: #d4af37;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }

    /* Divider */
    hr { border-color: #333 !important; }
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────────────────────────

def init_session():
    if "advisor" not in st.session_state:
        with st.spinner("Loading knowledge base..."):
            st.session_state.advisor = EnstuiAdvisor()

    if "messages" not in st.session_state:
        st.session_state.messages = []
        # Auto-send a greeting on first load
        greeting = st.session_state.advisor.chat(
            "Introduce yourself briefly as the Enstui Ou Strategic Advisor "
            "and ask me for my situation, goal, and the last message received."
        )
        st.session_state.messages.append({"role": "assistant", "content": greeting})

    if "situation_mode" not in st.session_state:
        st.session_state.situation_mode = False


init_session()


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="advisor-header">
    <h1>👑 ENSTUI OU</h1>
    <p>Strategic Advisor — Powered by real channel content</p>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🎯 Quick Situation Entry")
    st.markdown("Fill in all three fields for the best analysis:")

    st.markdown('<p class="situation-label">The Situation</p>', unsafe_allow_html=True)
    situation = st.text_area(
        "situation",
        placeholder="What just happened? (e.g. She replied with one word after days...)",
        height=90,
        label_visibility="collapsed"
    )

    st.markdown('<p class="situation-label">Your Goal</p>', unsafe_allow_html=True)
    goal = st.text_input(
        "goal",
        placeholder="What do you want to happen next?",
        label_visibility="collapsed"
    )

    st.markdown('<p class="situation-label">The Evidence</p>', unsafe_allow_html=True)
    evidence = st.text_area(
        "evidence",
        placeholder='Paste the last message (e.g. Her: "ok")',
        height=70,
        label_visibility="collapsed"
    )

    if st.button("⚡ Analyze My Situation"):
        if situation:
            combined = (
                f"SITUATION: {situation}\n\n"
                f"MY GOAL: {goal or 'Not specified'}\n\n"
                f"LAST MESSAGE: {evidence or 'Not provided'}"
            )
            st.session_state._pending_input = combined
        else:
            st.warning("Fill in at least the Situation field.")

    st.divider()

    # Stats
    advisor = st.session_state.advisor
    try:
        from retriever import get_source_stats
        stats = get_source_stats(advisor.supabase)
        st.markdown("### 📊 Knowledge Base")
        col1, col2 = st.columns(2)
        col1.metric("Videos", len(stats["videos"]))
        col2.metric("Books", len(stats["books"]))
        st.caption(f"{stats['total_chunks']:,} total chunks indexed")
    except Exception:
        st.caption("Knowledge base connected")

    st.divider()
    st.markdown("### 🗂 Pages")
    st.page_link("app.py",                        label="👑 Advisor Chat")
    st.page_link("pages/1_📚_Upload_Books.py",    label="📚 Upload Books")
    st.page_link("pages/2_🗄️_Knowledge_Base.py", label="🗄️ Knowledge Base")

    st.divider()

    msg_count = advisor.message_count
    st.caption(f"Session: {msg_count} message{'s' if msg_count != 1 else ''}")

    if st.button("🔄 Reset Conversation"):
        advisor.reset()
        greeting = advisor.chat(
            "Introduce yourself briefly as the Enstui Ou Strategic Advisor "
            "and ask me for my situation, goal, and the last message received."
        )
        st.session_state.messages = [{"role": "assistant", "content": greeting}]
        st.rerun()


# ── Chat Display ──────────────────────────────────────────────────────────────

chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        role    = msg["role"]
        avatar  = "👑" if role == "assistant" else "🧑"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg["content"])


# ── Handle Sidebar Quick-Submit ───────────────────────────────────────────────

if "_pending_input" in st.session_state:
    pending = st.session_state.pop("_pending_input")

    st.session_state.messages.append({"role": "user", "content": pending})

    with st.spinner("Analyzing your situation..."):
        reply = st.session_state.advisor.chat(pending)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


# ── Chat Input ────────────────────────────────────────────────────────────────

user_input = st.chat_input("Describe your situation or ask a question...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.spinner("Consulting the knowledge base..."):
        try:
            reply = st.session_state.advisor.chat(user_input)
        except Exception as e:
            reply = f"⚠️ Error: {e}\n\nMake sure your API keys are set in `.env`."

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
