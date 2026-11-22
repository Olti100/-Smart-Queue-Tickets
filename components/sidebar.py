import streamlit as st

from database.models import Role


ROLE_MODULES = {
    Role.ADMIN.value: ["Customer Portal", "Receptionist Dashboard", "Staff Dashboard", "Public Queue Display", "Manager/Admin Dashboard"],
    Role.MANAGER.value: ["Customer Portal", "Public Queue Display", "Manager/Admin Dashboard"],
    Role.RECEPTIONIST.value: ["Customer Portal", "Receptionist Dashboard", "Public Queue Display"],
    Role.STAFF.value: ["Staff Dashboard", "Public Queue Display"],
    Role.CUSTOMER.value: ["Customer Portal", "Public Queue Display"],
}


def render_sidebar(user: dict | None) -> str:
    st.sidebar.image("assets/logo.png", width=140)
    st.sidebar.title("Smart Queue Tickets")

    if user:
        st.sidebar.caption(f"Signed in as: {user['full_name']} ({user['role']})")
        modules = ROLE_MODULES.get(user["role"], ["Customer Portal"])
    else:
        modules = ["Customer Portal", "Public Queue Display"]

    return st.sidebar.radio("Navigate", modules)
