from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from database.models import Setting
from modules.authentication import require_roles


def render(session, user: dict):
    if not require_roles(["ADMIN"]):
        return

    st.title("Settings")
    st.caption("Local configuration settings")

    key = st.text_input("Setting Key")
    value = st.text_input("Setting Value")

    if st.button("Save Setting") and key:
        row = session.scalar(select(Setting).where(Setting.key == key))
        if row:
            row.value = value
        else:
            session.add(Setting(key=key, value=value))
        session.commit()
        st.success("Setting saved")

    rows = session.scalars(select(Setting)).all()
    for row in rows:
        st.write(f"{row.key}: {row.value}")
