from database.bootstrap import bootstrap_database


def test_admin_can_view_database_panel(client):
    bootstrap_database()
    client.post("/login", data={"username": "admin", "password": "admin123"})

    response = client.get("/database?table=tickets")
    assert response.status_code == 200


def test_database_csv_export(client):
    bootstrap_database()
    client.post("/login", data={"username": "manager", "password": "manager123"})

    response = client.get("/database/export/tickets")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"


def test_customer_cannot_view_database_panel(client):
    bootstrap_database()
    client.post("/login", data={"username": "staff", "password": "staff123"})

    response = client.get("/database", follow_redirects=False)
    assert response.status_code in {302, 403}


def test_reset_requires_exact_confirmation(client):
    bootstrap_database()
    client.post("/login", data={"username": "admin", "password": "admin123"})

    response = client.post(
        "/database/reset-operational",
        data={"confirmation": "wrong"},
        follow_redirects=True,
    )
    assert response.status_code == 200
