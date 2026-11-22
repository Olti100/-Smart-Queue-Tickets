from __future__ import annotations

from pathlib import Path

import streamlit as st

from components.sidebar import render_sidebar
from database.bootstrap import bootstrap_database
from database.connection import get_session
from modules import customer_portal, manager_dashboard, queue_display, receptionist, staff_dashboard
from modules.authentication import login_form, logout_button


st.set_page_config(page_title="Smart Queue Tickets", layout="wide", initial_sidebar_state="expanded")


def load_css() -> None:
    css_path = Path("assets/styles.css")
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def main() -> None:
    bootstrap_database()
    load_css()

    with get_session() as session:
        user = st.session_state.get("user")

        if not user:
            st.title("Smart Queue Tickets")
            st.caption("Professional local queue management platform")
            login_form(session)
            st.divider()
            st.subheader("Continue as Guest")
            customer_portal.render(session, None)
            return

        logout_button()
        selected_module = render_sidebar(user)

        if selected_module == "Customer Portal":
            customer_portal.render(session, user)
        elif selected_module == "Receptionist Dashboard":
            receptionist.render(session, user)
        elif selected_module == "Staff Dashboard":
            staff_dashboard.render(session, user)
        elif selected_module == "Public Queue Display":
            queue_display.render(session, user)
        elif selected_module == "Manager/Admin Dashboard":
            manager_dashboard.render(session, user)


if __name__ == "__main__":
    main()
