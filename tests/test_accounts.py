from database.bootstrap import bootstrap_database
from database.connection import SessionLocal
from database.models import Role, User


def test_register_and_login(client):
    bootstrap_database()
    with SessionLocal() as session:
        existing = session.query(User).filter_by(username="hackathon_user").first()
        if existing:
            session.delete(existing)
            session.commit()

    response = client.post("/register", data={
        "full_name": "Hackathon User",
        "username": "hackathon_user",
        "password": "secure123",
        "confirm_password": "secure123",
    }, follow_redirects=True)

    assert response.status_code == 200

    with SessionLocal() as session:
        user = session.query(User).filter_by(username="hackathon_user").first()
        assert user is not None
        assert user.role == Role.CUSTOMER

    client.get("/logout")
    response = client.post("/login", data={
        "username": "hackathon_user",
        "password": "secure123",
    }, follow_redirects=True)

    assert response.status_code == 200


def test_duplicate_registration_is_rejected(client):
    bootstrap_database()
    response = client.post("/register", data={
        "full_name": "Duplicate User",
        "username": "admin",
        "password": "secure123",
        "confirm_password": "secure123",
    }, follow_redirects=True)

    assert response.status_code == 200
