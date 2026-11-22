from database.bootstrap import bootstrap_database
from database.connection import SessionLocal
from database.models import Department, Service, Ticket, TicketEvent
from services.ticket_service import TicketService


def test_unique_ticket_numbers():
    bootstrap_database()
    with SessionLocal() as session:
        session.query(TicketEvent).delete()
        session.query(Ticket).delete()
        session.commit()

        dept = session.query(Department).first()
        service = session.query(Service).filter_by(department_id=dept.id).first()
        svc = TicketService(session)

        t1 = svc.create_ticket(department_id=dept.id, service_id=service.id)
        t2 = svc.create_ticket(department_id=dept.id, service_id=service.id)
        session.commit()

        assert t1.ticket_number != t2.ticket_number
