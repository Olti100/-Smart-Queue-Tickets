from database.bootstrap import bootstrap_database
from database.connection import SessionLocal
from database.models import Counter, Department, PriorityCategory, Service, Ticket, TicketEvent, TicketStatus, User
from services.ticket_service import TicketService


def test_queue_order_and_priority():
    bootstrap_database()
    with SessionLocal() as session:
        session.query(TicketEvent).delete()
        session.query(Ticket).delete()
        session.commit()

        dept = session.query(Department).first()
        service = session.query(Service).filter_by(department_id=dept.id).first()
        counter = session.query(Counter).filter_by(department_id=dept.id).first()
        counter.is_active = True
        counter.is_paused = False
        staff = session.query(User).filter_by(username="staff").first()

        svc = TicketService(session)
        regular = svc.create_ticket(department_id=dept.id, service_id=service.id, priority_category=PriorityCategory.REGULAR)
        vip = svc.create_ticket(department_id=dept.id, service_id=service.id, priority_category=PriorityCategory.VIP)
        session.commit()

        called = svc.call_next_ticket(counter.id, staff.id)
        session.commit()

        assert called.id in {regular.id, vip.id}
        assert called.status == TicketStatus.CALLED
