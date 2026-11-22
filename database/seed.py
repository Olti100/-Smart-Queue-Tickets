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
        ("Emergency Triage", "E"),
        ("Banking & Accounts", "N"),
        ("Government Services", "G"),
        ("University Services", "U"),
        ("Customer Support", "C"),
        ("Human Resources", "H"),
        ("IT Help Desk", "I"),
        ("Document Services", "D"),
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
        ("General Consultation", "Specialist Referral", "REF", 12),
        ("Laboratory", "Blood Test", "BLD", 8),
        ("Laboratory", "Imaging", "IMG", 14),
        ("Laboratory", "Test Results", "RES", 6),
        ("Billing", "Payment", "PAY", 5),
        ("Billing", "Insurance Claim", "INS", 12),
        ("Billing", "Invoice Inquiry", "INV", 7),
        ("Pharmacy", "Medicine Pickup", "MED", 6),
        ("Pharmacy", "Prescription Advice", "ADV", 8),
        ("Emergency Triage", "Urgent Assessment", "URG", 5),
        ("Emergency Triage", "Accident Intake", "ACC", 9),
        ("Banking & Accounts", "Account Opening", "OPN", 15),
        ("Banking & Accounts", "Cash Deposit", "DEP", 7),
        ("Banking & Accounts", "Loan Consultation", "LON", 18),
        ("Banking & Accounts", "Card Support", "CRD", 10),
        ("Government Services", "ID Application", "ID", 12),
        ("Government Services", "Permit Processing", "PER", 14),
        ("Government Services", "Tax Assistance", "TAX", 16),
        ("Government Services", "Civil Records", "REC", 10),
        ("University Services", "Admission Inquiry", "ADM", 12),
        ("University Services", "Student Registration", "REG", 10),
        ("University Services", "Academic Advising", "ADV2", 16),
        ("University Services", "Transcript Request", "TRN", 8),
        ("Customer Support", "General Inquiry", "GEN", 8),
        ("Customer Support", "Complaint Resolution", "CMP", 12),
        ("Customer Support", "Order Assistance", "ORD", 9),
        ("Human Resources", "Job Application", "JOB", 10),
        ("Human Resources", "Employee Records", "EMP", 8),
        ("Human Resources", "Leave Request", "LEV", 7),
        ("IT Help Desk", "Password Reset", "PWD", 6),
        ("IT Help Desk", "Hardware Support", "HW", 15),
        ("IT Help Desk", "Software Support", "SW", 12),
        ("Document Services", "Printing", "PRT", 5),
        ("Document Services", "Certification", "CRT", 10),
        ("Document Services", "Document Review", "REV", 12),
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
        ("Triage Desk", "Emergency Triage"),
        ("Bank Desk 1", "Banking & Accounts"),
        ("Bank Desk 2", "Banking & Accounts"),
        ("Government Desk 1", "Government Services"),
        ("Government Desk 2", "Government Services"),
        ("University Desk 1", "University Services"),
        ("University Desk 2", "University Services"),
        ("Support Desk", "Customer Support"),
        ("HR Desk", "Human Resources"),
        ("IT Desk", "IT Help Desk"),
        ("Document Desk", "Document Services"),
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
