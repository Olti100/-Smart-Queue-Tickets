from datetime import datetime, time

from sqlalchemy import func, select

from database.models import Department, Ticket


def generate_ticket_number(session, department_id: int) -> str:
    department = session.get(Department, department_id)
    if not department:
        raise ValueError("Department not found")

    now = datetime.utcnow()
    day_start = datetime.combine(now.date(), time.min)
    day_end = datetime.combine(now.date(), time.max)

    count_today = session.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.department_id == department_id,
            Ticket.created_at >= day_start,
            Ticket.created_at <= day_end,
        )
    )
    sequence = (count_today or 0) + 1
    return f"{department.code}{sequence:03d}"
