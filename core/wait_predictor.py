from datetime import datetime

from sqlalchemy import func, select

from database.models import Counter, Service, Ticket, TicketStatus


class WaitPredictor:
    def __init__(self, session):
        self.session = session

    def estimate_wait_minutes(self, department_id: int, service_id: int) -> int:
        waiting_count = self.session.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.department_id == department_id,
                Ticket.status == TicketStatus.WAITING,
            )
        ) or 0

        active_counters = self.session.scalar(
            select(func.count(Counter.id)).where(
                Counter.department_id == department_id,
                Counter.is_active.is_(True),
                Counter.is_paused.is_(False),
            )
        ) or 1

        service = self.session.get(Service, service_id)
        base_duration = service.average_duration_minutes if service else 8

        historical_avg = self.session.scalar(
            select(func.avg(
                (func.julianday(Ticket.completed_at) - func.julianday(Ticket.service_started_at)) * 24 * 60
            )).where(
                Ticket.department_id == department_id,
                Ticket.status == TicketStatus.COMPLETED,
                Ticket.service_started_at.is_not(None),
                Ticket.completed_at.is_not(None),
            )
        )
        avg_duration = float(historical_avg) if historical_avg else float(base_duration)

        estimated = (waiting_count * avg_duration) / max(active_counters, 1)
        return max(int(round(estimated)), 1) if waiting_count > 0 else 0

    def people_ahead(self, ticket: Ticket) -> int:
        return self.session.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.department_id == ticket.department_id,
                Ticket.status == TicketStatus.WAITING,
                Ticket.created_at < ticket.created_at,
            )
        ) or 0

    def smart_counter_recommendation(self, department_id: int) -> str | None:
        waiting_count = self.session.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.department_id == department_id,
                Ticket.status == TicketStatus.WAITING,
            )
        ) or 0
        active_counters = self.session.scalar(
            select(func.count(Counter.id)).where(
                Counter.department_id == department_id,
                Counter.is_active.is_(True),
                Counter.is_paused.is_(False),
            )
        ) or 1
        ratio = waiting_count / max(active_counters, 1)
        if ratio >= 8:
            return "High demand detected. Opening an additional counter is recommended."
        return None
