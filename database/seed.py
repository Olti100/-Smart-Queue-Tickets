from __future__ import annotations

import bcrypt
from sqlalchemy import select

from .models import Counter, Department, Role, Service, User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_initial_data(session) -> None:
    departments = [
        ("General Consultation", "A"),
        ("Laboratory", "L"),
        ("Billing", "B"),
        ("Pharmacy", "P"),
    ]

    for name, code in departments:
        exists = session.scalar(select(Department).where(Department.name == name))
        if not exists:
            session.add(Department(name=name, code=code))
    session.flush()

    dept_map = {d.name: d for d in session.scalars(select(Department)).all()}

    services = [
        ("General Consultation", "Checkup", "CHK", 10),
        ("General Consultation", "Follow-up", "FLW", 7),
        ("Laboratory", "Blood Test", "BLD", 8),
        ("Laboratory", "Imaging", "IMG", 14),
        ("Billing", "Payment", "PAY", 5),
        ("Pharmacy", "Medicine Pickup", "MED", 6),
    ]

    for dept_name, service_name, code, avg_duration in services:
        dept = dept_map[dept_name]
        exists = session.scalar(
            select(Service).where(
                Service.department_id == dept.id,
                Service.name == service_name,
            )
        )
        if not exists:
            session.add(
                Service(
                    department_id=dept.id,
                    name=service_name,
                    code=code,
                    average_duration_minutes=avg_duration,
                )
            )

    counters = [
        ("Counter 1", "General Consultation"),
        ("Counter 2", "General Consultation"),
        ("Counter 3", "Laboratory"),
        ("Counter 4", "Billing"),
        ("Counter 5", "Pharmacy"),
    ]

    for counter_name, dept_name in counters:
        dept = dept_map[dept_name]
        exists = session.scalar(select(Counter).where(Counter.name == counter_name))
        if not exists:
            session.add(Counter(name=counter_name, department_id=dept.id))

    demo_users = [
        ("System Admin", "admin", "admin123", Role.ADMIN),
        ("Queue Manager", "manager", "manager123", Role.MANAGER),
        ("Front Desk", "reception", "reception123", Role.RECEPTIONIST),
        ("Service Staff", "staff", "staff123", Role.STAFF),
    ]

    for full_name, username, password, role in demo_users:
        exists = session.scalar(select(User).where(User.username == username))
        if not exists:
            session.add(
                User(
                    full_name=full_name,
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                    is_active=True,
                )
            )
