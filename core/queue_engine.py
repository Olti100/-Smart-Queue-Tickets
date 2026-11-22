from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from core.priority_manager import should_force_regular, ticket_priority_score
from core.ticket_generator import generate_ticket_number
from core.wait_predictor import WaitPredictor
from database.models import (
    Counter,
    Department,
    PriorityCategory,
    Service,
    Ticket,
    TicketEvent,
    TicketStatus,
    TicketType,
)


class QueueEngine:
    def __init__(self, session):
        self.session = session

    def create_ticket(
        self,
        department_id: int,
        service_id: int,
        customer_name: str | None = None,
        priority_category: PriorityCategory = PriorityCategory.REGULAR,
        ticket_type: TicketType = TicketType.WALK_IN,
        created_by_user_id: int | None = None,
    ) -> Ticket:
        ticket_number = generate_ticket_number(self.session, department_id)
        predictor = WaitPredictor(self.session)
        estimated_wait = predictor.estimate_wait_minutes(department_id, service_id)

        ticket = Ticket(
            ticket_number=ticket_number,
            customer_name=customer_name,
            priority_category=priority_category,
            ticket_type=ticket_type,
            department_id=department_id,
            service_id=service_id,
            estimated_wait_minutes=estimated_wait,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(ticket)
        self.session.flush()
        self._event(ticket.id, "CREATED", "Ticket generated", created_by_user_id)
        return ticket

    def _waiting_candidates(self, department_id: int | None = None) -> list[Ticket]:
        stmt = select(Ticket).where(Ticket.status == TicketStatus.WAITING)
        if department_id:
            stmt = stmt.where(Ticket.department_id == department_id)
        stmt = stmt.order_by(Ticket.created_at.asc())
        return list(self.session.scalars(stmt).all())

    def _pick_next_ticket(self, candidates: list[Ticket]) -> Ticket | None:
        if not candidates:
            return None
        force_regular = should_force_regular(candidates)
        if force_regular:
            return force_regular
        return max(candidates, key=ticket_priority_score)

    def call_next_ticket(self, counter_id: int, staff_user_id: int) -> Ticket | None:
        counter = self.session.get(Counter, counter_id)
        if not counter or not counter.is_active or counter.is_paused:
            return None

        candidates = self._waiting_candidates(counter.department_id)
        next_ticket = self._pick_next_ticket(candidates)
        if not next_ticket:
            return None

        next_ticket.status = TicketStatus.CALLED
        next_ticket.counter_id = counter_id
        next_ticket.called_by_staff_id = staff_user_id
        next_ticket.called_at = datetime.utcnow()
        self.session.flush()

        self._event(next_ticket.id, "CALLED", f"Called to {counter.name}", staff_user_id)
        return next_ticket

    def start_service(self, ticket_id: int, staff_user_id: int) -> Ticket:
        ticket = self.session.get(Ticket, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        ticket.status = TicketStatus.SERVING
        ticket.service_started_at = datetime.utcnow()
        self._event(ticket.id, "SERVING", "Service started", staff_user_id)
        return ticket

    def complete_service(self, ticket_id: int, staff_user_id: int) -> Ticket:
        ticket = self.session.get(Ticket, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        ticket.status = TicketStatus.COMPLETED
        ticket.completed_at = datetime.utcnow()
        self._event(ticket.id, "COMPLETED", "Service completed", staff_user_id)
        return ticket

    def skip_ticket(self, ticket_id: int, staff_user_id: int, reason: str) -> Ticket:
        ticket = self.session.get(Ticket, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        ticket.status = TicketStatus.SKIPPED
        ticket.skip_reason = reason
        self._event(ticket.id, "SKIPPED", reason, staff_user_id)
        return ticket

    def recall_ticket(self, ticket_id: int, staff_user_id: int) -> Ticket:
        ticket = self.session.get(Ticket, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        ticket.status = TicketStatus.CALLED
        ticket.recall_count += 1
        self._event(ticket.id, "RECALLED", "Ticket recalled", staff_user_id)
        return ticket

    def cancel_ticket(self, ticket_id: int, user_id: int, reason: str = "Cancelled") -> Ticket:
        ticket = self.session.get(Ticket, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        ticket.status = TicketStatus.CANCELLED
        self._event(ticket.id, "CANCELLED", reason, user_id)
        return ticket

    def transfer_ticket(
        self,
        ticket_id: int,
        target_department_id: int,
        target_service_id: int,
        user_id: int,
        note: str = "",
    ) -> Ticket:
        ticket = self.session.get(Ticket, ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        ticket.status = TicketStatus.TRANSFERRED
        ticket.transfer_note = note
        self._event(ticket.id, "TRANSFERRED", note, user_id)

        new_ticket = self.create_ticket(
            department_id=target_department_id,
            service_id=target_service_id,
            customer_name=ticket.customer_name,
            priority_category=ticket.priority_category,
            ticket_type=ticket.ticket_type,
            created_by_user_id=user_id,
        )
        self._event(new_ticket.id, "TRANSFER_IN", f"From {ticket.ticket_number}", user_id)
        return new_ticket

    def set_counter_pause(self, counter_id: int, paused: bool) -> Counter:
        counter = self.session.get(Counter, counter_id)
        if not counter:
            raise ValueError("Counter not found")
        counter.is_paused = paused
        return counter

    def ticket_snapshot(self, ticket_number: str) -> dict:
        ticket = self.session.scalar(select(Ticket).where(Ticket.ticket_number == ticket_number))
        if not ticket:
            raise ValueError("Ticket not found")

        currently_serving = self.session.scalar(
            select(Ticket)
            .where(
                Ticket.department_id == ticket.department_id,
                Ticket.status.in_([TicketStatus.SERVING, TicketStatus.CALLED]),
            )
            .order_by(desc(Ticket.called_at), desc(Ticket.service_started_at))
        )

        predictor = WaitPredictor(self.session)
        return {
            "ticket": ticket,
            "currently_serving": currently_serving,
            "people_ahead": predictor.people_ahead(ticket),
            "estimated_wait": predictor.estimate_wait_minutes(ticket.department_id, ticket.service_id),
        }

    def recent_calls(self, department_id: int | None = None, limit: int = 12) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .where(Ticket.status.in_([TicketStatus.CALLED, TicketStatus.SERVING]))
            .order_by(desc(Ticket.called_at), desc(Ticket.updated_at))
            .limit(limit)
        )
        if department_id:
            stmt = stmt.where(Ticket.department_id == department_id)
        return list(self.session.scalars(stmt).all())

    def _event(self, ticket_id: int, event_type: str, note: str | None, user_id: int | None) -> None:
        self.session.add(
            TicketEvent(
                ticket_id=ticket_id,
                event_type=event_type,
                note=note,
                performed_by_user_id=user_id,
            )
        )
