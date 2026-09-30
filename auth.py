"""Simple SQLite login via Streamlit session state. No JWT."""

from __future__ import annotations

import streamlit as st

from config import AI_INFERENCE_LABEL
from database import authenticate_user, init_db, log_action, AUDIT_LOGIN
from ui import banner, html, inject_styles


def current_user() -> dict | None:
    return st.session_state.get("user")


def can_access_department(user: dict | None, department: str) -> bool:
    """Basic department check. Admin may open any department in this demo."""
    if not user:
        return False
    if user.get("role") == "Admin":
        return True
    return user.get("department") == department


def login(username: str, password: str) -> dict | None:
    init_db()
    user = authenticate_user(username, password)
    if not user:
        return None
    st.session_state.user = user
    log_action(user["username"], user["department"], AUDIT_LOGIN, f"{user['role']} signed in")
    return user


def logout() -> None:
    user = current_user()
    if user:
        log_action(user["username"], user["department"], "logout", "Signed out")
    st.session_state.pop("user", None)


def render_login() -> None:
    init_db()
    inject_styles()
    html(
        """
        <div class="indus-login-wrap">
          <div class="indus-login-card">
            <div class="indus-brand">INDUSAI</div>
            <div class="indus-brand-sub">Industrial AI Workbench</div>
          </div>
        </div>
        """
    )

    left, mid, right = st.columns([1, 2.2, 1])
    with mid:
        banner(f"{AI_INFERENCE_LABEL} · External model — prototype")
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="engineer")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("SIGN IN", use_container_width=True, type="primary")

        if submitted:
            user = login(username, password)
            if user:
                st.rerun()
            st.error("Unknown username or password. Check the demo accounts below.")

        st.markdown(
            '<p class="indus-muted">Demo accounts · password <code>demo123</code></p>',
            unsafe_allow_html=True,
        )
        st.caption("`admin` · `engineer` · `reviewer` — SQLite hashed passwords, no JWT")
