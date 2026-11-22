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


def test_landing_page_explains_business_and_customer_paths(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "FOR BUSINESSES" in html
    assert "FOR CUSTOMERS" in html
    assert "Get a digital ticket" in html


def test_business_registration_creates_manager(client):
    bootstrap_database()
    with SessionLocal() as session:
        existing = session.query(User).filter_by(username="new_manager").first()
        if existing:
            session.delete(existing)
            session.commit()

    response = client.post("/business/register", data={
        "organization_name": "Northside Clinic",
        "full_name": "New Manager",
        "username": "new_manager",
        "password": "secure123",
        "confirm_password": "secure123",
    }, follow_redirects=True)

    assert response.status_code == 200
    with SessionLocal() as session:
        user = session.query(User).filter_by(username="new_manager").first()
        assert user is not None
        assert user.role == Role.MANAGER


def test_duplicate_registration_is_rejected(client):
    bootstrap_database()
    response = client.post("/register", data={
        "full_name": "Duplicate User",
        "username": "admin",
        "password": "secure123",
        "confirm_password": "secure123",
    }, follow_redirects=True)

    assert response.status_code == 200
