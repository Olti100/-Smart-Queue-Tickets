from __future__ import annotations

from datetime import datetime

import streamlit as st
from sqlalchemy import desc, select

from core.queue_engine import QueueEngine
from database.models import Counter, Department, Ticket, TicketStatus
from services.notification_service import voice_notifier


def render(session, user: dict | None):
    st.title("Public Queue Display")
    st.caption("Live waiting-room board")

    departments = session.scalars(select(Department)).all()
    dep_map = {"All": None, **{d.name: d.id for d in departments}}
    selected = st.selectbox("Department", list(dep_map.keys()), index=0)
    department_id = dep_map[selected]

    if st.button("Refresh"):
        st.rerun()

    st.markdown(f"### {datetime.now().strftime('%H:%M:%S')}")

    engine = QueueEngine(session)
    called = engine.recent_calls(department_id=department_id, limit=9)

    st.subheader("Currently Serving")
    serve_cols = st.columns(3)
    for idx, ticket in enumerate(called[:3]):
        counter = session.get(Counter, ticket.counter_id) if ticket.counter_id else None
        with serve_cols[idx % 3]:
            st.markdown(
                f"""
                <div class='serving-box'>
                    <div class='serving-ticket'>{ticket.ticket_number}</div>
                    <div class='serving-counter'>{counter.name if counter else 'Unassigned'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.subheader("Next Tickets")
    waiting_stmt = select(Ticket).where(Ticket.status == TicketStatus.WAITING).order_by(Ticket.created_at.asc()).limit(6)
    if department_id:
        waiting_stmt = waiting_stmt.where(Ticket.department_id == department_id)
    waiting = session.scalars(waiting_stmt).all()
    st.write(" ".join([t.ticket_number for t in waiting]) if waiting else "No waiting tickets")

    st.subheader("Recently Called")
    for ticket in called[:8]:
        counter = session.get(Counter, ticket.counter_id) if ticket.counter_id else None
        st.write(f"{ticket.ticket_number} - {counter.name if counter else 'N/A'}")

    announce = st.text_input("Announcement")
    if st.button("Speak Announcement") and announce:
        voice_notifier.announce(announce)

    if st.checkbox("Auto voice for latest call") and called:
        latest = called[0]
        counter = session.get(Counter, latest.counter_id) if latest.counter_id else None
        msg = f"Ticket {latest.ticket_number}, please proceed to {counter.name if counter else 'your counter'}."
        voice_notifier.announce(msg)
