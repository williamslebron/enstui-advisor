"""
streamlit_cloud.py

Tiny helpers that make the app run cleanly on both:
  • Local development   — reads keys from .env via python-dotenv
  • Streamlit Community Cloud — reads keys from st.secrets

Call load_secrets() once at the very top of every Streamlit entry point
(app.py and pages/*.py), BEFORE importing advisor / retriever / kb_manager.
Then optionally call require_password() to gate access.

Both functions are safe to call multiple times and degrade gracefully
if run outside of Streamlit.
"""

import os


def load_secrets() -> None:
    """
    Populate os.environ from both .env (local) and st.secrets (Streamlit Cloud).
    Existing os.getenv() calls in advisor / retriever / kb_manager will Just Work.
    """
    # 1. Local: read .env via python-dotenv (no-op on Streamlit Cloud — no .env there)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    # 2. Cloud: copy st.secrets into os.environ
    try:
        import streamlit as st
        # Accessing st.secrets raises FileNotFoundError when no secrets are defined
        # (which is the normal local case). Swallow that.
        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return
        try:
            items = list(secrets.items())
        except Exception:
            return
        for key, value in items:
            # Don't overwrite anything .env already set
            if key not in os.environ:
                os.environ[key] = str(value)
    except Exception:
        pass


def require_password() -> None:
    """
    Prompt for APP_PASSWORD before letting the user interact with the app.
    If APP_PASSWORD is not set, the gate is silently skipped (open access).
    Call once near the top of each Streamlit entry point, AFTER load_secrets().
    """
    try:
        import streamlit as st
    except ImportError:
        return

    expected = os.getenv("APP_PASSWORD", "").strip()
    if not expected:
        # No password configured — open access (useful for local dev)
        return

    # Already authenticated in this session
    if st.session_state.get("_password_ok"):
        return

    st.markdown(
        """
        <style>
          .pw-wrap { max-width: 360px; margin: 15vh auto 0; text-align: center; }
          .pw-wrap h2 { color: #d4af37; font-weight: 700; margin-bottom: 0.4rem; }
          .pw-wrap p  { color: #888; font-size: 0.9rem; }
        </style>
        <div class="pw-wrap">
          <h2>👑 Enstui Ou</h2>
          <p>Enter password to continue</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pw = st.text_input("Password", type="password", label_visibility="collapsed")

    if pw == "":
        st.stop()

    if pw == expected:
        st.session_state["_password_ok"] = True
        st.rerun()
    else:
        st.error("Incorrect password")
        st.stop()
