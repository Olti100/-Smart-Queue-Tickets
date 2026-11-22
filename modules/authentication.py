from __future__ import annotations

import bcrypt
from sqlalchemy import select

from database.models import User


def verify_password(raw_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _st():
    import streamlit as st

    return st


def login_form(session):
    st = _st()
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")

    if submitted:
        user = session.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if user and verify_password(password, user.password_hash):
            st.session_state["user"] = {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role.value,
                "assigned_counter_id": user.assigned_counter_id,
            }
            st.success("Login successful")
            st.rerun()
        st.error("Invalid credentials")


def logout_button():
    st = _st()
    if st.sidebar.button("Logout"):
        st.session_state.pop("user", None)
        st.rerun()


def require_roles(allowed_roles: list[str]) -> bool:
    st = _st()
    user = st.session_state.get("user")
    if not user:
        st.warning("Please login to access this module.")
        return False
    if user["role"] not in allowed_roles:
        st.error("You do not have permission to access this section.")
        return False
    return True
