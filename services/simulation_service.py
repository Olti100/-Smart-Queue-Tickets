from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass

from faker import Faker
from sqlalchemy import select

from core.queue_engine import QueueEngine
from database.connection import SessionLocal
from database.models import Counter, Department, PriorityCategory, Service, User


faker = Faker()


@dataclass
class SimulationState:
    running: bool = False
    speed_seconds: float = 1.5


class SimulationService:
    def __init__(self):
        self.state = SimulationState()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.state.running:
            return
        self.state.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.state.running = False

    def _run_loop(self) -> None:
        while self.state.running:
            with SessionLocal() as session:
                engine = QueueEngine(session)
                departments = session.scalars(select(Department)).all()
                if not departments:
                    time.sleep(self.state.speed_seconds)
                    continue

                department = random.choice(departments)
                services = session.scalars(select(Service).where(Service.department_id == department.id)).all()
                counters = session.scalars(select(Counter).where(Counter.department_id == department.id)).all()
                staff = session.scalar(select(User).where(User.role == "STAFF"))

                if services:
                    engine.create_ticket(
                        department_id=department.id,
                        service_id=random.choice(services).id,
                        customer_name=faker.name(),
                        priority_category=random.choice(
                            [PriorityCategory.REGULAR, PriorityCategory.VIP, PriorityCategory.APPOINTMENT]
                        ),
                    )

                if counters and staff and random.random() > 0.3:
                    next_ticket = engine.call_next_ticket(random.choice(counters).id, staff.id)
                    if next_ticket and random.random() > 0.4:
                        engine.start_service(next_ticket.id, staff.id)
                    if next_ticket and random.random() > 0.55:
                        engine.complete_service(next_ticket.id, staff.id)

                session.commit()
            time.sleep(self.state.speed_seconds)


simulation_service = SimulationService()
