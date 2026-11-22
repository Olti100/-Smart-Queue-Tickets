from __future__ import annotations

import streamlit as st
from sqlalchemy import desc, func, or_, select

from core.queue_engine import QueueEngine
from database.models import Department, PriorityCategory, Service, Ticket, TicketStatus
from modules.authentication import require_roles
from services.ticket_service import TicketService


def render(session, user: dict):
    if not require_roles(["ADMIN", "MANAGER", "RECEPTIONIST"]):
        return

    st.title("Receptionist Dashboard")

    create_col, manage_col = st.columns(2)

    with create_col:
        st.subheader("Register Walk-in")
        departments = session.scalars(select(Department).where(Department.is_active.is_(True))).all()
        dep_map = {d.name: d for d in departments}
        dep_name = st.selectbox("Department", list(dep_map.keys()), key="r_dep")
        dep = dep_map[dep_name]
        services = session.scalars(select(Service).where(Service.department_id == dep.id)).all()
        svc_map = {s.name: s for s in services}
        svc_name = st.selectbox("Service", list(svc_map.keys()), key="r_svc")

        customer_name = st.text_input("Customer Name", key="r_name")
        priority = st.selectbox("Priority", [c.value for c in PriorityCategory], key="r_priority")

        if st.button("Generate Ticket", key="r_generate"):
            ticket = TicketService(session).create_ticket(
                department_id=dep.id,
                service_id=svc_map[svc_name].id,
                customer_name=customer_name or None,
                priority_category=PriorityCategory(priority),
                created_by_user_id=user["id"],
            )
            session.commit()
            st.success(f"Ticket generated: {ticket.ticket_number}")

    with manage_col:
        st.subheader("Search and Manage")
        q = st.text_input("Search ticket number or customer")
        stmt = select(Ticket).order_by(desc(Ticket.created_at)).limit(50)
        if q:
            stmt = stmt.where(
                or_(
                    Ticket.ticket_number.ilike(f"%{q}%"),
                    Ticket.customer_name.ilike(f"%{q}%"),
                )
            )
        rows = session.scalars(stmt).all()

        for ticket in rows[:20]:
            with st.container(border=True):
                st.write(f"{ticket.ticket_number} | {ticket.department.name} | {ticket.status.value}")
                col1, col2 = st.columns(2)
                if col1.button("Cancel", key=f"cancel_{ticket.id}") and ticket.status == TicketStatus.WAITING:
                    QueueEngine(session).cancel_ticket(ticket.id, user["id"], "Cancelled by receptionist")
                    session.commit()
                    st.success("Ticket cancelled")
                    st.rerun()

                target_services = session.scalars(select(Service)).all()
                service_labels = [f"{s.department.name} - {s.name}" for s in target_services]
                chosen = col2.selectbox("Transfer to", service_labels, key=f"transferto_{ticket.id}")
                if col2.button("Transfer", key=f"transfer_{ticket.id}") and ticket.status in [TicketStatus.WAITING, TicketStatus.CALLED]:
                    idx = service_labels.index(chosen)
                    svc = target_services[idx]
                    QueueEngine(session).transfer_ticket(ticket.id, svc.department_id, svc.id, user["id"], "Transferred by receptionist")
                    session.commit()
                    st.success("Ticket transferred")
                    st.rerun()

    st.divider()
    waiting_count = session.scalar(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.WAITING))
    completed_count = session.scalar(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.COMPLETED))
    st.metric("Waiting Customers", waiting_count or 0)
    st.metric("Completed Customers", completed_count or 0)
