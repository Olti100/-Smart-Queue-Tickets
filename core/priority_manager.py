from datetime import datetime

from database.models import PriorityCategory, Ticket


PRIORITY_WEIGHTS = {
    PriorityCategory.VIP: 30,
    PriorityCategory.APPOINTMENT: 20,
    PriorityCategory.REGULAR: 10,
}


def ticket_priority_score(ticket: Ticket, now: datetime | None = None) -> float:
    now = now or datetime.utcnow()
    waited_minutes = max((now - ticket.created_at).total_seconds() / 60.0, 0)
    base = PRIORITY_WEIGHTS[ticket.priority_category]
    # Aging factor prevents regular tickets from starving.
    return base + (waited_minutes * 0.45)


def should_force_regular(waiting_tickets: list[Ticket], now: datetime | None = None) -> Ticket | None:
    now = now or datetime.utcnow()
    regulars = [t for t in waiting_tickets if t.priority_category == PriorityCategory.REGULAR]
    if not regulars:
        return None
    regulars.sort(key=lambda t: t.created_at)
    oldest_regular = regulars[0]
    waited = (now - oldest_regular.created_at).total_seconds() / 60.0
    return oldest_regular if waited >= 25 else None
