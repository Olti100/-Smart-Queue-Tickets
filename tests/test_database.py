from database.bootstrap import bootstrap_database
from database.connection import SessionLocal
from database.models import Department, User


def test_database_seeded():
    bootstrap_database()
    with SessionLocal() as session:
        assert session.query(Department).count() >= 1
        assert session.query(User).count() >= 1
