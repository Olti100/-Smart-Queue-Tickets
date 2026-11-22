from __future__ import annotations

from io import BytesIO

import streamlit as st
from sqlalchemy import select

from core.queue_engine import QueueEngine
from database.models import CustomerFeedback, Department, PriorityCategory, Service, Ticket
from services.pdf_service import generate_ticket_pdf
from services.qr_service import generate_qr_bytes
from services.ticket_service import TicketService


def render(session, user: dict | None):
    st.title("Customer Portal")
    st.caption("Generate and track your digital queue ticket")

    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Generate Ticket")
        departments = session.scalars(select(Department).where(Department.is_active.is_(True))).all()
        dept_map = {d.name: d for d in departments}
        department_name = st.selectbox("Department", list(dept_map.keys()))
        department = dept_map[department_name]

        services = session.scalars(
            select(Service).where(Service.department_id == department.id, Service.is_active.is_(True))
        ).all()
        service_map = {s.name: s for s in services}
        service_name = st.selectbox("Service", list(service_map.keys()))
        service = service_map[service_name]

        customer_name = st.text_input("Customer Name (Optional)")
        priority = st.selectbox("Priority Category", [c.value for c in PriorityCategory])

        if st.button("Generate Digital Ticket", type="primary"):
            ticket_service = TicketService(session)
            ticket = ticket_service.create_ticket(
                department_id=department.id,
                service_id=service.id,
                customer_name=customer_name or None,
                priority_category=PriorityCategory(priority),
                created_by_user_id=user["id"] if user else None,
            )
            session.commit()
            st.session_state["last_ticket_number"] = ticket.ticket_number
            st.success(f"Ticket generated: {ticket.ticket_number}")

    with right:
        st.subheader("Track Ticket")
        lookup = st.text_input("Ticket Number", value=st.session_state.get("last_ticket_number", ""))
        if st.button("Check Status") and lookup:
            engine = QueueEngine(session)
            try:
                snapshot = engine.ticket_snapshot(lookup.strip().upper())
            except ValueError:
                st.error("Ticket not found")
            else:
                ticket = snapshot["ticket"]
                serving = snapshot["currently_serving"]
                st.info(f"Ticket: {ticket.ticket_number}")
                st.write(f"Department: {ticket.department.name}")
                st.write(f"Currently Serving: {serving.ticket_number if serving else 'N/A'}")
                st.write(f"People Ahead: {snapshot['people_ahead']}")
                st.write(f"Estimated Waiting Time: {snapshot['estimated_wait']} minutes")
                st.write(f"Status: {ticket.status.value}")

                qr_data = generate_qr_bytes(ticket.ticket_number)
                st.image(qr_data, caption="Ticket QR Code", width=180)

                pdf = generate_ticket_pdf(
                    ticket=ticket,
                    org_name="Smart Queue Organization",
                    department_name=ticket.department.name,
                    service_name=ticket.service.name,
                    estimated_wait=snapshot["estimated_wait"],
                )
                st.download_button(
                    "Download PDF Ticket",
                    data=BytesIO(pdf),
                    file_name=f"ticket_{ticket.ticket_number}.pdf",
                    mime="application/pdf",
                )

    st.divider()
    st.subheader("Customer Satisfaction")
    with st.form("feedback_form"):
        feedback_ticket = st.text_input("Ticket Number for Feedback")
        rating = st.slider("Rating", 1, 5, 5)
        comment = st.text_area("Comment")
        submitted = st.form_submit_button("Submit Feedback")

    if submitted and feedback_ticket:
        ticket = session.scalar(select(Ticket).where(Ticket.ticket_number == feedback_ticket.strip().upper()))
        if not ticket:
            st.error("Ticket not found")
        else:
            existing = session.scalar(select(CustomerFeedback).where(CustomerFeedback.ticket_id == ticket.id))
            if existing:
                existing.rating = rating
                existing.comment = comment
            else:
                session.add(CustomerFeedback(ticket_id=ticket.id, rating=rating, comment=comment))
            session.commit()
            st.success("Thank you for your feedback")
