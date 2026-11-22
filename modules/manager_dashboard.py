from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import func, select

from components.cards import kpi_card
from core.analytics_engine import AnalyticsEngine
from core.wait_predictor import WaitPredictor
from database.models import Counter, Department, Service, Ticket, TicketStatus
from modules.authentication import require_roles
from services.simulation_service import simulation_service


def render(session, user: dict):
    if not require_roles(["ADMIN", "MANAGER"]):
        return

    st.title("Manager/Admin Dashboard")

    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("Start date", value=datetime.utcnow().date() - timedelta(days=7))
    with col_b:
        end_date = st.date_input("End date", value=datetime.utcnow().date())

    departments = session.scalars(select(Department).where(Department.is_active.is_(True))).all()
    dept_options = {"All": None, **{d.name: d.id for d in departments}}
    selected_dept_label = st.selectbox("Department Filter", list(dept_options.keys()))
    selected_dept = dept_options[selected_dept_label]

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    analytics = AnalyticsEngine(session)
    kpis = analytics.kpis(start_dt, end_dt, selected_dept)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total Tickets", str(kpis["total_tickets"]))
    with c2:
        kpi_card("Waiting", str(kpis["waiting"]), "#F59E0B")
    with c3:
        kpi_card("Serving", str(kpis["serving"]), "#2563EB")
    with c4:
        kpi_card("Completed", str(kpis["completed"]), "#16A34A")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        kpi_card("Cancelled", str(kpis["cancelled"]), "#DC2626")
    with c6:
        kpi_card("Avg Wait (min)", f"{kpis['avg_wait']}")
    with c7:
        kpi_card("Avg Service (min)", f"{kpis['avg_service']}")
    with c8:
        kpi_card("Satisfaction", f"{kpis['avg_satisfaction']} / 5")

    st.write(f"Completion Rate: {kpis['completion_rate']}%")
    st.write(f"Abandonment Rate: {kpis['abandonment_rate']}%")

    tickets_df = analytics.tickets_dataframe(start_dt, end_dt)
    peak_df = analytics.peak_hours(start_dt, end_dt)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        if not peak_df.empty:
            fig = px.bar(peak_df, x="hour", y="tickets", title="Peak Customer Arrival Hours")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No peak hour data in selected range.")

    with chart_col2:
        if not tickets_df.empty:
            dept_perf = tickets_df.groupby("department", as_index=False).size().rename(columns={"size": "tickets"})
            fig = px.pie(dept_perf, names="department", values="tickets", title="Department Performance")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No department data in selected range.")

    st.subheader("Smart Recommendations")
    predictor = WaitPredictor(session)
    if selected_dept:
        recommendation = predictor.smart_counter_recommendation(selected_dept)
        if recommendation:
            st.warning(recommendation)
        else:
            st.success("Current counter capacity looks healthy.")

    st.subheader("Live Queue Simulation")
    sim_col1, sim_col2 = st.columns(2)
    if sim_col1.button("Start Simulation"):
        simulation_service.start()
        st.success("Simulation started")
    if sim_col2.button("Stop Simulation"):
        simulation_service.stop()
        st.warning("Simulation stopped")

    if st.button("Demo Mode: Generate Sample Tickets"):
        service = session.scalar(select(Service))
        if service:
            from services.ticket_service import TicketService

            svc = TicketService(session)
            for _ in range(30):
                svc.create_ticket(
                    department_id=service.department_id,
                    service_id=service.id,
                    customer_name="Demo Customer",
                )
            session.commit()
            st.success("Sample data created")

    st.subheader("Counter and Employee Performance")
    counter_stats = session.execute(
        select(Counter.name, func.count(Ticket.id))
        .join(Ticket, Ticket.counter_id == Counter.id, isouter=True)
        .where(Ticket.status == TicketStatus.COMPLETED)
        .group_by(Counter.id)
    ).all()
    if counter_stats:
        cdf = pd.DataFrame(counter_stats, columns=["counter", "completed"])
        fig = px.bar(cdf, x="counter", y="completed", title="Counter Performance")
        st.plotly_chart(fig, use_container_width=True)
