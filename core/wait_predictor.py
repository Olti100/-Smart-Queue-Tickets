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

    def queue_weather(self, department_id: int | None = None) -> dict:
        waiting_query = select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.WAITING)
        counter_query = select(func.count(Counter.id)).where(
            Counter.is_active.is_(True),
            Counter.is_paused.is_(False),
        )
        if department_id:
            waiting_query = waiting_query.where(Ticket.department_id == department_id)
            counter_query = counter_query.where(Counter.department_id == department_id)

        waiting_count = self.session.scalar(waiting_query) or 0
        active_counters = self.session.scalar(counter_query) or 0
        workload = waiting_count / max(active_counters, 1)

        if workload <= 3:
            return {"label": "CALM", "level": "calm", "waiting": waiting_count, "workload": workload}
        if workload <= 8:
            return {"label": "BUSY", "level": "busy", "waiting": waiting_count, "workload": workload}
        return {"label": "CRITICAL", "level": "critical", "waiting": waiting_count, "workload": workload}

    def smart_coach(self) -> list[dict]:
        from database.models import Department

        recommendations = []
        departments = self.session.scalars(select(Department).where(Department.is_active.is_(True))).all()
        for department in departments:
            waiting_count = self.session.scalar(
                select(func.count(Ticket.id)).where(
                    Ticket.department_id == department.id,
                    Ticket.status == TicketStatus.WAITING,
                )
            ) or 0
            active_counters = self.session.scalar(
                select(func.count(Counter.id)).where(
                    Counter.department_id == department.id,
                    Counter.is_active.is_(True),
                    Counter.is_paused.is_(False),
                )
            ) or 0

            average_wait = self.session.scalar(
                select(func.avg(Ticket.estimated_wait_minutes)).where(
                    Ticket.department_id == department.id,
                    Ticket.status == TicketStatus.WAITING,
                )
            )

            if waiting_count >= 10 and active_counters > 0:
                action = f"Open an additional counter in {department.name}."
                impact = f"Could reduce the estimated wait by about {max(int((waiting_count * 5) / (active_counters + 1)), 5)} minutes."
                severity = "high"
            elif waiting_count >= 5:
                action = f"Prepare for the next surge in {department.name}."
                impact = f"Keep at least one staff member ready; {waiting_count} customers are waiting."
                severity = "medium"
            else:
                action = f"{department.name} has healthy coverage."
                impact = f"Current waiting queue is {waiting_count}."
                severity = "low"

            recommendations.append({
                "department": department.name,
                "waiting": waiting_count,
                "active_counters": active_counters,
                "average_wait": int(round(float(average_wait or 0))),
                "action": action,
                "impact": impact,
                "severity": severity,
            })
        return recommendations
