from database.bootstrap import bootstrap_database
from database.connection import SessionLocal
from database.models import User
from modules.authentication import verify_password


def test_demo_user_authentication():
    bootstrap_database()
    with SessionLocal() as session:
        admin = session.query(User).filter_by(username="admin").first()
        assert admin is not None
        assert verify_password("admin123", admin.password_hash)
