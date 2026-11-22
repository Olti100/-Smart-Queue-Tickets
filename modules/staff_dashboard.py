from __future__ import annotations

import streamlit as st
from sqlalchemy import desc, func, select

from core.queue_engine import QueueEngine
from database.models import Counter, Ticket, TicketStatus
from modules.authentication import require_roles
from services.ticket_service import TicketService


def render(session, user: dict):
    if not require_roles(["ADMIN", "MANAGER", "STAFF"]):
        return

    st.title("Staff Dashboard")
    counters = session.scalars(select(Counter).where(Counter.is_active.is_(True))).all()
    counter_map = {c.name: c for c in counters}

    selected_name = st.selectbox("Assigned Counter", list(counter_map.keys()))
    counter = counter_map[selected_name]

    engine = QueueEngine(session)
    ticket_service = TicketService(session)

    current_ticket = session.scalar(
        select(Ticket)
        .where(Ticket.counter_id == counter.id, Ticket.status.in_([TicketStatus.CALLED, TicketStatus.SERVING]))
        .order_by(desc(Ticket.called_at), desc(Ticket.updated_at))
    )

    st.write(f"Current Ticket: {current_ticket.ticket_number if current_ticket else 'None'}")

    c1, c2, c3 = st.columns(3)
    if c1.button("CALL NEXT", type="primary"):
        next_ticket = ticket_service.call_next_ticket(counter.id, user["id"])
        session.commit()
        if next_ticket:
            st.success(f"Called {next_ticket.ticket_number}")
        else:
            st.warning("No waiting tickets")
        st.rerun()

    if c2.button("START SERVICE") and current_ticket:
        engine.start_service(current_ticket.id, user["id"])
        session.commit()
        st.success("Service started")
        st.rerun()

    if c3.button("COMPLETE SERVICE") and current_ticket:
        engine.complete_service(current_ticket.id, user["id"])
        session.commit()
        st.success("Service completed")
        st.rerun()

    c4, c5, c6 = st.columns(3)
    if c4.button("RECALL") and current_ticket:
        engine.recall_ticket(current_ticket.id, user["id"])
        session.commit()
        st.info("Ticket recalled")

    skip_reason = st.text_input("Skip reason", value="No response")
    if c5.button("SKIP") and current_ticket:
        engine.skip_ticket(current_ticket.id, user["id"], skip_reason)
        session.commit()
        st.warning("Ticket skipped")
        st.rerun()

    transfer_to = st.number_input("Transfer target service ID", min_value=1, step=1)
    if c6.button("TRANSFER") and current_ticket:
        # Simplified transfer path for staff.
        target_service_id = int(transfer_to)
        from database.models import Service

        svc = session.get(Service, target_service_id)
        if svc:
            engine.transfer_ticket(current_ticket.id, svc.department_id, svc.id, user["id"], "Transferred by staff")
            session.commit()
            st.success("Ticket transferred")
            st.rerun()
        else:
            st.error("Invalid service ID")

    p1, p2 = st.columns(2)
    if p1.button("PAUSE COUNTER"):
        engine.set_counter_pause(counter.id, True)
        session.commit()
        st.warning("Counter paused")
    if p2.button("RESUME COUNTER"):
        engine.set_counter_pause(counter.id, False)
        session.commit()
        st.success("Counter resumed")

    st.divider()
    waiting = session.scalar(select(func.count(Ticket.id)).where(Ticket.department_id == counter.department_id, Ticket.status == TicketStatus.WAITING)) or 0
    completed = session.scalar(select(func.count(Ticket.id)).where(Ticket.counter_id == counter.id, Ticket.status == TicketStatus.COMPLETED)) or 0
    durations = session.execute(
        select((func.julianday(Ticket.completed_at) - func.julianday(Ticket.service_started_at)) * 24 * 60)
        .where(Ticket.counter_id == counter.id, Ticket.status == TicketStatus.COMPLETED)
    ).scalars().all()
    avg_duration = sum(durations) / len(durations) if durations else 0

    st.metric("Waiting Customers", int(waiting))
    st.metric("Completed Customers", int(completed))
    st.metric("Average Service Duration (min)", f"{avg_duration:.1f}")
