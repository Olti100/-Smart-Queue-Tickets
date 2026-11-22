from __future__ import annotations

from sqlalchemy import select

from core.queue_engine import QueueEngine
from core.wait_predictor import WaitPredictor
from database.models import Ticket, TicketStatus


class TicketService:
    def __init__(self, session):
        self.session = session
        self.queue_engine = QueueEngine(session)

    def create_ticket(self, **kwargs) -> Ticket:
        ticket = self.queue_engine.create_ticket(**kwargs)
        self.refresh_wait_predictions(ticket.department_id)
        return ticket

    def call_next_ticket(self, counter_id: int, staff_user_id: int):
        ticket = self.queue_engine.call_next_ticket(counter_id, staff_user_id)
        if ticket:
            self.refresh_wait_predictions(ticket.department_id)
        return ticket

    def refresh_wait_predictions(self, department_id: int) -> None:
        predictor = WaitPredictor(self.session)
        waiting_tickets = self.session.scalars(
            select(Ticket).where(Ticket.department_id == department_id, Ticket.status == TicketStatus.WAITING)
        ).all()
        for ticket in waiting_tickets:
            ticket.estimated_wait_minutes = predictor.estimate_wait_minutes(ticket.department_id, ticket.service_id)
