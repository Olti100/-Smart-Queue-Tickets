from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import func, select

from database.models import Counter, CustomerFeedback, Ticket, TicketStatus, User


class AnalyticsEngine:
    def __init__(self, session):
        self.session = session

    def kpis(self, start: datetime, end: datetime, department_id: int | None = None) -> dict:
        base = select(Ticket).where(Ticket.created_at >= start, Ticket.created_at <= end)
        if department_id:
            base = base.where(Ticket.department_id == department_id)

        tickets = list(self.session.scalars(base).all())
        total = len(tickets)
        waiting = len([t for t in tickets if t.status == TicketStatus.WAITING])
        serving = len([t for t in tickets if t.status in (TicketStatus.CALLED, TicketStatus.SERVING)])
        completed = len([t for t in tickets if t.status == TicketStatus.COMPLETED])
        cancelled = len([t for t in tickets if t.status == TicketStatus.CANCELLED])

        wait_values = [t.estimated_wait_minutes for t in tickets if t.estimated_wait_minutes is not None]
        avg_wait = float(sum(wait_values) / len(wait_values)) if wait_values else 0.0

        service_durations = [
            (t.completed_at - t.service_started_at).total_seconds() / 60
            for t in tickets
            if t.completed_at and t.service_started_at
        ]
        avg_service = float(sum(service_durations) / len(service_durations)) if service_durations else 0.0

        active_counters = self.session.scalar(
            select(func.count()).select_from(Counter).where(Counter.is_active.is_(True), Counter.is_paused.is_(False))
        ) or 0
        active_employees = self.session.scalar(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        ) or 0

        feedback_avg = self.session.scalar(
            select(func.avg(CustomerFeedback.rating)).where(CustomerFeedback.created_at >= start, CustomerFeedback.created_at <= end)
        )

        abandonment = (len([t for t in tickets if t.status in (TicketStatus.CANCELLED, TicketStatus.NO_SHOW)]) / total * 100.0) if total else 0.0
        completion_rate = (completed / total * 100.0) if total else 0.0

        return {
            "total_tickets": total,
            "waiting": waiting,
            "serving": serving,
            "completed": completed,
            "cancelled": cancelled,
            "avg_wait": round(avg_wait, 2),
            "avg_service": round(avg_service, 2),
            "active_counters": active_counters,
            "active_employees": active_employees,
            "avg_satisfaction": round(float(feedback_avg or 0.0), 2),
            "completion_rate": round(completion_rate, 2),
            "abandonment_rate": round(abandonment, 2),
        }

    def tickets_dataframe(self, start: datetime, end: datetime) -> pd.DataFrame:
        tickets = list(
            self.session.scalars(
                select(Ticket).where(Ticket.created_at >= start, Ticket.created_at <= end)
            ).all()
        )
        rows = [
            (
                t.ticket_number,
                t.created_at,
                t.status.value if hasattr(t.status, "value") else str(t.status),
                t.department.name if t.department else "Unknown",
            )
            for t in tickets
        ]
        if not rows:
            return pd.DataFrame(columns=["ticket_number", "created_at", "status", "department"])
        return pd.DataFrame(rows, columns=["ticket_number", "created_at", "status", "department"])

    def peak_hours(self, start: datetime, end: datetime) -> pd.DataFrame:
        df = self.tickets_dataframe(start, end)
        if df.empty:
            return pd.DataFrame(columns=["hour", "tickets"])
        df["hour"] = pd.to_datetime(df["created_at"]).dt.hour
        return df.groupby("hour", as_index=False).size().rename(columns={"size": "tickets"})
