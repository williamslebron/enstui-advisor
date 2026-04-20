"""
pages/3_📸_Analyze_Conversation.py

Upload screenshots of your text conversation.
The advisor reads every message, scores the power dynamic,
identifies every mistake, and gives you the exact action plan.
"""

import json
import streamlit as st

# ── Page Config — MUST be the first Streamlit call ────────────────────────────
st.set_page_config(
    page_title = "Analyze Conversation — Enstui Ou",
    page_icon  = "📸",
    layout     = "wide"
)

# Secrets bridge + password gate (must run before importing conversation_analyzer)
from streamlit_cloud import load_secrets, require_password
load_secrets()
require_password()

from conversation_analyzer import ConversationAnalyzer

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); color: #f0f0f0; }
    [data-testid="stSidebar"] { background: #111 !important; border-right: 1px solid #222; }
    hr { border-color: #333 !important; }

    .page-header { text-align:center; padding:1.5rem 0; border-bottom:1px solid #333; margin-bottom:2rem; }
    .page-header h1 { color:#d4af37; font-size:1.8rem; margin:0; }
    .page-header p  { color:#888; font-size:.9rem; margin-top:.4rem; }

    .power-meter {
        background: rgba(255,255,255,0.04);
        border:1px solid rgba(255,255,255,0.1);
        border-radius:14px; padding:1.5rem; text-align:center; margin-bottom:1rem;
    }
    .score-number { font-size:4rem; font-weight:800; line-height:1; }
    .score-label  { font-size:.9rem; color:#888; margin-top:.3rem; }

    .verdict-box {
        border-radius:12px; padding:1.1rem 1.4rem; margin:1rem 0;
        font-size:1.05rem; font-style:italic;
    }
    .verdict-good { background:rgba(34,197,94,.12); border-left:4px solid #22c55e; }
    .verdict-warn { background:rgba(234,179,8,.12);  border-left:4px solid #eab308; }
    .verdict-bad  { background:rgba(239,68,68,.12);  border-left:4px solid #ef4444; }

    .timeline-item {
        background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08);
        border-radius:10px; padding:.9rem 1.1rem; margin-bottom:.5rem;
    }
    .gained  { border-left:3px solid #22c55e; }
    .lost    { border-left:3px solid #ef4444; }
    .neutral { border-left:3px solid #888; }

    .mistake-card {
        border-radius:10px; padding:.9rem 1.1rem; margin:.4rem 0;
    }
    .sev-critical { background:rgba(239,68,68,.18); border:1px solid rgba(239,68,68,.4); }
    .sev-high     { background:rgba(249,115,22,.14); border:1px solid rgba(249,115,22,.35); }
    .sev-medium   { background:rgba(234,179,8,.12);  border:1px solid rgba(234,179,8,.3); }
    .sev-low      { background:rgba(148,163,184,.1); border:1px solid rgba(148,163,184,.25); }

    .action-step {
        background:rgba(212,175,55,.07); border:1px solid rgba(212,175,55,.25);
        border-radius:12px; padding:1.2rem 1.4rem; margin:.7rem 0;
    }
    .action-number { color:#d4af37; font-weight:800; font-size:1.2rem; }
    .timing-badge {
        display:inline-block; background:rgba(212,175,55,.2);
        border:1px solid rgba(212,175,55,.5); border-radius:20px;
        padding:.2rem .8rem; font-size:.8rem; color:#d4af37; font-weight:600;
    }
    .msg-box {
        background:rgba(0,0,0,.4); border:1px solid #333; border-radius:8px;
        padding:.7rem 1rem; font-family:monospace; font-size:.88rem;
        color:#e2e8f0; margin:.4rem 0;
    }
    .stButton>button {
        background:linear-gradient(135deg,#d4af37,#b8943f);
        color:#000; font-weight:700; border:none; border-radius:8px; width:100%;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
    <h1>📸 Conversation Analyzer</h1>
    <p>Upload screenshots. Get a full power dynamic breakdown + your exact action plan.</p>
</div>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

@st.cache_resource
def get_analyzer():
    return ConversationAnalyzer()

try:
    analyzer = get_analyzer()
except Exception as e:
    st.error(f"Could not initialize analyzer: {e}")
    st.stop()


# ── Upload form ───────────────────────────────────────────────────────────────

with st.form("analysis_form"):
    st.markdown("#### 📤 Upload Conversation Screenshots")
    st.caption("Upload 1–5 screenshots. The order you upload them is the order they are read.")

    uploaded_files = st.file_uploader(
        "Drop screenshots here",
        type             = ["jpg", "jpeg", "png", "webp"],
        accept_multiple_files = True,
        label_visibility = "collapsed"
    )

    col1, col2 = st.columns(2)
    with col1:
        user_context = st.text_area(
            "Context (optional but helps)",
            placeholder = "e.g. We dated 2 months, she started being cold 3 days ago, last met in person last week.",
            height = 90
        )
    with col2:
        goal = st.text_input(
            "Your Goal",
            placeholder = "e.g. Re-spark her interest and get her back"
        )
        her_name = st.text_input(
            "Her name (optional)",
            placeholder = "e.g. Melissa"
        )

    submitted = st.form_submit_button("⚡ Analyze My Conversation")

if submitted:
    if not uploaded_files:
        st.warning("Upload at least one screenshot.")
    else:
        images = [(f.read(), f.name) for f in uploaded_files]
        with st.spinner(f"Analyzing {len(images)} screenshot(s) — reading every message..."):
            try:
                result = analyzer.analyze(
                    images       = images,
                    user_context = user_context,
                    goal         = goal
                )
                st.session_state.analysis_result = result
                st.session_state.analysis_her_name = her_name or "her"
                st.session_state.analysis_situation = user_context
                st.session_state.analysis_goal = goal
            except Exception as e:
                st.error(f"Analysis failed: {e}")


# ── Display results ───────────────────────────────────────────────────────────

result = st.session_state.get("analysis_result")

if result:

    if result.get("parse_error"):
        st.markdown("### Analysis")
        st.markdown(result.get("raw_analysis", "No result"))
        st.stop()

    st.divider()

    # ── Power score + interest level ──────────────────────────────────
    c1, c2, c3 = st.columns(3)

    power    = result.get("power_score", 5)
    interest = result.get("her_interest_level", "UNKNOWN")
    color    = "#22c55e" if power >= 7 else "#eab308" if power >= 4 else "#ef4444"

    with c1:
        st.markdown(f"""
        <div class="power-meter">
            <div class="score-number" style="color:{color}">{power}/10</div>
            <div class="score-label">Power Score</div>
        </div>""", unsafe_allow_html=True)

    interest_color = {"HIGH":"#22c55e","MEDIUM":"#eab308","LOW":"#f97316","FADING":"#ef4444"}.get(interest,"#888")
    with c2:
        st.markdown(f"""
        <div class="power-meter">
            <div class="score-number" style="color:{interest_color};font-size:2rem;padding-top:.8rem">{interest}</div>
            <div class="score-label">Her Interest Level</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="power-meter" style="text-align:left;">
            <div style="color:#d4af37;font-size:.8rem;font-weight:700;letter-spacing:.08em;margin-bottom:.5rem">WHAT SHE IS DOING</div>
            <div style="font-size:.9rem;color:#e2e8f0">{result.get("what_she_is_doing","—")}</div>
        </div>""", unsafe_allow_html=True)

    # Verdict
    verdict      = result.get("overall_verdict", "")
    verdict_cls  = "verdict-good" if power >= 7 else "verdict-warn" if power >= 4 else "verdict-bad"
    st.markdown(f'<div class="verdict-box {verdict_cls}">"{verdict}"</div>', unsafe_allow_html=True)

    # Current position
    pos = result.get("his_current_position", "")
    if pos:
        st.markdown(f'<div style="color:#94a3b8;font-size:.9rem;margin-bottom:1rem">📍 {pos}</div>', unsafe_allow_html=True)

    st.divider()

    # ── Two column layout: timeline + mistakes ────────────────────────
    left, right = st.columns([3, 2])

    with left:
        st.markdown("#### 📋 Conversation Timeline")
        timeline = result.get("timeline", [])
        if timeline:
            for item in timeline:
                impact    = item.get("impact", "NEUTRAL")
                css_class = {"GAINED_VALUE":"gained","LOST_VALUE":"lost"}.get(impact,"neutral")
                icon      = {"GAINED_VALUE":"✅","LOST_VALUE":"❌","NEUTRAL":"➖"}.get(impact,"➖")
                st.markdown(f"""
                <div class="timeline-item {css_class}">
                    <div style="font-weight:600">{icon} {item.get('moment','')}</div>
                    <div style="color:#94a3b8;font-size:.85rem;margin:.3rem 0">{item.get('what_happened','')}</div>
                    <div style="color:#d4af37;font-size:.8rem">🎯 {item.get('why','')}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.caption("No timeline data")

    with right:
        st.markdown("#### ⚠️ Mistakes Made")
        mistakes = result.get("critical_mistakes", [])
        if mistakes:
            for m in mistakes:
                sev     = m.get("severity","LOW").upper()
                css_sev = {"CRITICAL":"sev-critical","HIGH":"sev-high","MEDIUM":"sev-medium","LOW":"sev-low"}.get(sev,"sev-low")
                st.markdown(f"""
                <div class="mistake-card {css_sev}">
                    <div style="font-weight:700;font-size:.85rem">{sev}: {m.get('mistake','')}</div>
                    <div style="color:#94a3b8;font-size:.8rem;margin-top:.3rem">
                        Violates: {m.get('technique_violated','')}
                    </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("No critical mistakes identified")

    st.divider()

    # ── Action Plan ───────────────────────────────────────────────────
    st.markdown("#### 🎯 Your Action Plan")

    action_plan = result.get("action_plan", [])
    for step in action_plan:
        st.markdown(f"""
        <div class="action-step">
            <div style="display:flex;align-items:center;gap:.8rem;margin-bottom:.7rem">
                <span class="action-number">Step {step.get('step')}</span>
                <span class="timing-badge">⏰ {step.get('timing','')}</span>
            </div>
            <div style="font-weight:600;margin-bottom:.5rem">{step.get('action','')}</div>
            <div style="color:#94a3b8;font-size:.82rem;margin-bottom:.7rem">
                🎯 Technique: {step.get('why','')}
            </div>
        """, unsafe_allow_html=True)

        if step.get("message_option_a"):
            st.markdown(f'<div style="color:#64748b;font-size:.78rem;margin-bottom:.2rem">OPTION A — Direct:</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="msg-box">{step["message_option_a"]}</div>', unsafe_allow_html=True)
        if step.get("message_option_b"):
            st.markdown(f'<div style="color:#64748b;font-size:.78rem;margin-bottom:.2rem">OPTION B — Mystery:</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="msg-box">{step["message_option_b"]}</div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # Overall strategy
    overall = result.get("overall_strategy", "")
    if overall:
        st.markdown(f"""
        <div style="background:rgba(212,175,55,.08);border:1px solid rgba(212,175,55,.2);
             border-radius:12px;padding:1.2rem;margin-top:1rem">
            <div style="color:#d4af37;font-size:.8rem;font-weight:700;letter-spacing:.08em;margin-bottom:.5rem">
                OVERALL STRATEGY
            </div>
            <div style="color:#e2e8f0">{overall}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── Send to Autopilot ─────────────────────────────────────────────
    st.markdown("#### 🤖 Turn This Into an Autopilot Campaign")
    st.markdown("Let the system execute the action plan while you're away — messages sent at the exact right time.")

    if st.button("🚀 Create Autopilot Campaign from This Analysis"):
        st.session_state["autopilot_prefill"] = {
            "situation": st.session_state.get("analysis_situation", ""),
            "goal":      st.session_state.get("analysis_goal", ""),
            "her_name":  st.session_state.get("analysis_her_name", ""),
            "analysis":  result
        }
        st.success("✅ Data saved. Go to the 🤖 Autopilot page to generate the campaign.")
