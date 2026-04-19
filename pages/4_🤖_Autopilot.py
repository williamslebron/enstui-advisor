"""
pages/4_🤖_Autopilot.py

Autopilot Campaign Manager.
Set your strategy, leave — the system sends messages at exactly the right time.
Optional: connect Twilio to actually send SMS/WhatsApp automatically.
"""

import json
import streamlit as st
from datetime import datetime, timezone

# Secrets bridge + password gate (must run before importing autopilot)
from streamlit_cloud import load_secrets, require_password
load_secrets()
require_password()

from autopilot import AutopilotManager, load_campaigns, update_campaign

st.set_page_config(
    page_title = "Autopilot — Enstui Ou",
    page_icon  = "🤖",
    layout     = "wide"
)

st.markdown("""
<style>
    .stApp { background:linear-gradient(135deg,#0a0a0a 0%,#1a1a2e 100%); color:#f0f0f0; }
    [data-testid="stSidebar"] { background:#111 !important; border-right:1px solid #222; }
    hr { border-color:#333 !important; }

    .page-header { text-align:center; padding:1.5rem 0; border-bottom:1px solid #333; margin-bottom:2rem; }
    .page-header h1 { color:#d4af37; font-size:1.8rem; margin:0; }
    .page-header p  { color:#888; font-size:.9rem; margin-top:.4rem; }

    .campaign-card {
        background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08);
        border-radius:14px; padding:1.3rem 1.5rem; margin-bottom:1rem;
    }
    .campaign-active   { border-left:4px solid #22c55e; }
    .campaign-paused   { border-left:4px solid #eab308; }
    .campaign-completed{ border-left:4px solid #4a90d9; }
    .campaign-aborted  { border-left:4px solid #ef4444; }

    .msg-step {
        background:rgba(0,0,0,.3); border:1px solid rgba(255,255,255,.08);
        border-radius:10px; padding:.9rem 1.1rem; margin:.5rem 0;
    }
    .step-pending       { border-left:3px solid #888; }
    .step-ready_to_send { border-left:3px solid #d4af37; background:rgba(212,175,55,.08); }
    .step-sent          { border-left:3px solid #22c55e; }
    .step-skipped       { border-left:3px solid #64748b; opacity:.6; }

    .timing-badge {
        display:inline-block; background:rgba(212,175,55,.15);
        border:1px solid rgba(212,175,55,.35); border-radius:20px;
        padding:.15rem .7rem; font-size:.78rem; color:#d4af37;
    }
    .sent-badge {
        display:inline-block; background:rgba(34,197,94,.15);
        border:1px solid rgba(34,197,94,.35); border-radius:20px;
        padding:.15rem .7rem; font-size:.78rem; color:#22c55e;
    }
    .rule-box {
        background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.07);
        border-radius:8px; padding:.6rem 1rem; margin:.3rem 0;
        font-size:.85rem; color:#94a3b8;
    }
    .stButton>button {
        background:linear-gradient(135deg,#d4af37,#b8943f);
        color:#000; font-weight:700; border:none; border-radius:8px; width:100%;
    }
    .abort-btn>button { background:rgba(239,68,68,.8) !important; color:#fff !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
    <h1>🤖 Autopilot</h1>
    <p>Set your strategy. Leave. The system executes at exactly the right time.</p>
</div>
""", unsafe_allow_html=True)

# ── Init ──────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_manager():
    m = AutopilotManager()
    m.start_background_scheduler(interval_seconds=60)
    return m

manager = get_manager()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_new, tab_active, tab_sms = st.tabs(["✨ New Campaign", "📋 Active Campaigns", "📱 SMS Setup"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Create new campaign
# ══════════════════════════════════════════════════════════════════════════════
with tab_new:
    st.markdown("#### 🎯 Define Your Strategy")

    # Pre-fill from conversation analyzer if available
    prefill = st.session_state.pop("autopilot_prefill", {})

    with st.form("new_campaign"):
        col1, col2 = st.columns(2)
        with col1:
            situation = st.text_area(
                "The Situation",
                value       = prefill.get("situation", ""),
                placeholder = "What is the current state? Where things stand between you two right now.",
                height      = 120
            )
            her_name = st.text_input(
                "Her Name",
                value       = prefill.get("her_name", ""),
                placeholder = "e.g. Melissa"
            )
        with col2:
            goal = st.text_area(
                "Your Goal",
                value       = prefill.get("goal", ""),
                placeholder = "What outcome do you want from this campaign?",
                height      = 120
            )

        twilio_ok = bool(
            st.session_state.get("twilio_configured") or
            (manager.send_via_twilio("test","test").get("error","") != "Twilio not configured")
        )
        if twilio_ok:
            to_number = st.text_input(
                "Send to phone number (with country code)",
                placeholder = "+15551234567",
                help        = "Messages will be sent automatically to this number via Twilio"
            )
        else:
            to_number = ""
            st.info("📱 SMS not configured. Messages will queue here for you to send manually. Set up Twilio in the SMS Setup tab to enable auto-sending.")

        generate_btn = st.form_submit_button("🧠 Generate Autopilot Campaign")

    if generate_btn:
        if not situation or not goal:
            st.warning("Fill in Situation and Goal to generate a campaign.")
        else:
            with st.spinner("Building your campaign using Enstui Ou strategy..."):
                try:
                    campaign = manager.generate_campaign(
                        situation     = situation,
                        goal          = goal,
                        her_name      = her_name or "her",
                        analysis_data = prefill.get("analysis")
                    )
                    if to_number:
                        update_campaign(campaign["id"], {"to_number": to_number})
                    st.success(f"✅ Campaign **{campaign['campaign_name']}** created! ({len(campaign.get('messages',[]))} messages scheduled)")
                    st.session_state["view_campaign_id"] = campaign["id"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate campaign: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Active campaigns
# ══════════════════════════════════════════════════════════════════════════════
with tab_active:
    campaigns = load_campaigns()
    active    = [c for c in campaigns if c["status"] in ("active", "paused")]
    past      = [c for c in campaigns if c["status"] in ("completed", "aborted")]

    if not campaigns:
        st.info("No campaigns yet. Create one in the '✨ New Campaign' tab.")
    else:
        if active:
            st.markdown("#### ⚡ Running / Paused")
            for c in active:
                status_cls = f"campaign-{c['status']}"
                sms_label  = "📱 SMS AUTO-SEND" if c.get("sms_enabled") and c.get("to_number") else "📋 MANUAL QUEUE"
                st.markdown(f"""
                <div class="campaign-card {status_cls}">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div>
                            <span style="color:#d4af37;font-weight:700;font-size:1.05rem">{c.get('campaign_name','Campaign')}</span>
                            <span style="color:#888;font-size:.8rem;margin-left:.8rem">ID: {c['id']}</span>
                        </div>
                        <div>
                            <span style="color:#888;font-size:.78rem">{sms_label}</span>
                            <span style="margin-left:.5rem;color:{'#22c55e' if c['status']=='active' else '#eab308'};font-weight:700">
                                {c['status'].upper()}
                            </span>
                        </div>
                    </div>
                    <div style="color:#94a3b8;font-size:.85rem;margin:.5rem 0">{c.get('strategy_summary','')}</div>
                </div>""", unsafe_allow_html=True)

                # Message queue
                with st.expander(f"📨 Message Queue — {c.get('campaign_name')}"):
                    for msg in c.get("messages", []):
                        step_status = msg["status"]
                        css_step    = f"step-{step_status}"
                        send_label  = msg.get("send_at_label", "")
                        send_iso    = msg.get("send_at_iso", "")

                        # Time until send
                        try:
                            send_dt   = datetime.fromisoformat(send_iso)
                            now_dt    = datetime.now(timezone.utc)
                            delta     = send_dt - now_dt
                            if delta.total_seconds() > 0:
                                hrs  = int(delta.total_seconds() // 3600)
                                mins = int((delta.total_seconds() % 3600) // 60)
                                time_str = f"in {hrs}h {mins}m"
                            else:
                                time_str = "NOW"
                        except Exception:
                            time_str = ""

                        badge = f'<span class="sent-badge">✓ SENT</span>' if step_status == "sent" else \
                                f'<span class="timing-badge">⏰ {send_label} ({time_str})</span>' if step_status == "pending" else \
                                f'<span class="timing-badge" style="color:#d4af37">📋 READY TO SEND</span>' if step_status == "ready_to_send" else \
                                f'<span style="color:#64748b">⏭ SKIPPED</span>'

                        st.markdown(f"""
                        <div class="msg-step {css_step}">
                            <div style="display:flex;justify-content:space-between;margin-bottom:.4rem">
                                <span style="color:#d4af37;font-weight:700">Step {msg['step']}</span>
                                {badge}
                            </div>
                            <div style="font-family:monospace;background:rgba(0,0,0,.3);padding:.6rem .8rem;border-radius:6px;margin:.4rem 0">
                                {msg['message_text']}
                            </div>
                            <div style="color:#64748b;font-size:.78rem">
                                🎯 {msg.get('technique','')} — {msg.get('purpose','')}
                            </div>
                        </div>""", unsafe_allow_html=True)

                        # Manual send button for ready_to_send messages
                        if step_status == "ready_to_send":
                            col_copy, col_skip = st.columns(2)
                            with col_copy:
                                if st.button(f"📋 Copy Message", key=f"copy_{c['id']}_{msg['step']}"):
                                    st.code(msg["message_text"])
                                    st.caption("Copy the message above and send it manually.")
                            with col_skip:
                                if st.button(f"⏭ Mark Sent", key=f"marksent_{c['id']}_{msg['step']}"):
                                    manager.skip_message(c["id"], msg["step"])
                                    st.rerun()

                    # Campaign controls
                    st.markdown("---")
                    ctrl1, ctrl2, ctrl3 = st.columns(3)
                    with ctrl1:
                        if c["status"] == "active":
                            if st.button("⏸ Pause", key=f"pause_{c['id']}"):
                                manager.pause_campaign(c["id"]); st.rerun()
                        else:
                            if st.button("▶️ Resume", key=f"resume_{c['id']}"):
                                manager.resume_campaign(c["id"]); st.rerun()
                    with ctrl2:
                        if st.button("⏭ Skip Next", key=f"skip_{c['id']}"):
                            next_msg = next((m for m in c.get("messages",[]) if m["status"]=="pending"), None)
                            if next_msg:
                                manager.skip_message(c["id"], next_msg["step"]); st.rerun()
                    with ctrl3:
                        if st.button("🛑 Abort Campaign", key=f"abort_{c['id']}"):
                            manager.abort_campaign(c["id"]); st.rerun()

                    # Rules
                    rules = c.get("rules_while_away", [])
                    if rules:
                        st.markdown("**📏 Rules While Away:**")
                        for r in rules:
                            st.markdown(f'<div class="rule-box">• {r}</div>', unsafe_allow_html=True)

        if past:
            st.markdown("#### 📁 Past Campaigns")
            for c in past:
                sent = sum(1 for m in c.get("messages",[]) if m["status"]=="sent")
                st.markdown(f"""
                <div class="campaign-card campaign-{c['status']}" style="opacity:.7">
                    <span style="font-weight:600">{c.get('campaign_name','')}</span>
                    <span style="color:#888;font-size:.82rem;margin-left:.8rem">
                        {c['status'].upper()} · {sent} messages sent · ID: {c['id']}
                    </span>
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SMS / WhatsApp setup
# ══════════════════════════════════════════════════════════════════════════════
with tab_sms:
    st.markdown("#### 📱 Twilio SMS / WhatsApp Setup")
    st.markdown("""
Connecting Twilio lets the autopilot **actually send messages to her phone** at the exact scheduled time — even when you're not at your computer.

Without Twilio, the system still queues messages and shows you exactly what to send and when — you just copy and paste manually.
""")

    with st.expander("How to set up Twilio (free trial available)"):
        st.markdown("""
1. Go to [twilio.com](https://www.twilio.com) and create a free account
2. Get a free phone number (can send SMS to any number after verification)
3. From your dashboard, copy:
   - **Account SID**
   - **Auth Token**
   - **Your Twilio phone number** (format: +15551234567)
4. Add them to your `.env` file:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+15551234567
```

5. For WhatsApp: enable the Twilio Sandbox for WhatsApp in your dashboard.
   The `from` number format changes to: `whatsapp:+14155238886`

**Cost:** ~$0.0075 per SMS message (essentially free for personal use)
""")

    import os
    from dotenv import load_dotenv
    load_dotenv()

    sid   = os.getenv("TWILIO_ACCOUNT_SID","")
    token = os.getenv("TWILIO_AUTH_TOKEN","")
    frm   = os.getenv("TWILIO_FROM_NUMBER","")

    if sid and token and frm and not sid.startswith("your_"):
        st.success(f"✅ Twilio configured — sending from {frm}")
        st.session_state["twilio_configured"] = True
    else:
        st.warning("Twilio not configured. Add keys to .env to enable auto-sending.")
        st.caption("Without Twilio, messages will queue here for manual copy-paste.")
