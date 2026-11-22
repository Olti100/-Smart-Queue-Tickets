from database.bootstrap import bootstrap_database
from database.connection import SessionLocal
from database.models import Ticket
from core.wait_predictor import WaitPredictor


def test_queue_weather_and_smart_coach():
    bootstrap_database()
    with SessionLocal() as session:
        predictor = WaitPredictor(session)
        weather = predictor.queue_weather()
        coach = predictor.smart_coach()

        assert weather["label"] in {"CALM", "BUSY", "CRITICAL"}
        assert isinstance(weather["waiting"], int)
        assert isinstance(coach, list)
        assert all("action" in item and "impact" in item for item in coach)


def test_queue_arena_does_not_change_ticket_count(client):
    bootstrap_database()
    client.post("/login", data={"username": "admin", "password": "admin123"})

    with SessionLocal() as session:
        before = session.query(Ticket).count()

    normal = client.post("/arena/simulate?scenario=normal").get_json()
    surge = client.post("/arena/simulate?scenario=surge").get_json()

    assert normal["arena"]["incoming"] < surge["arena"]["incoming"]
    assert surge["arena"]["projected_queue"] >= normal["arena"]["projected_queue"]

    with SessionLocal() as session:
        after = session.query(Ticket).count()

    assert after == before


def test_queue_arena_custom_controls(client):
    bootstrap_database()
    client.post("/login", data={"username": "admin", "password": "admin123"})

    with SessionLocal() as session:
        before = session.query(Ticket).count()

    response = client.post("/arena/simulate", json={
        "scenario": "surge",
        "incoming": 50,
        "active_counters": 3,
        "service_speed": 150,
    })

    assert response.status_code == 200
    arena = response.get_json()["arena"]
    assert arena["incoming"] == 50
    assert arena["active_counters"] == 3
    assert arena["service_speed"] == 150
    assert arena["projected_queue"] >= 50
    assert arena["projected_wait"] >= 0
    assert arena["weather"] in {"CALM", "BUSY", "CRITICAL"}

    with SessionLocal() as session:
        after = session.query(Ticket).count()

    assert after == before


def test_queue_arena_control_bounds(client):
    bootstrap_database()
    client.post("/login", data={"username": "admin", "password": "admin123"})

    response = client.post("/arena/simulate", json={
        "incoming": 999,
        "active_counters": 99,
        "service_speed": 999,
    })

    assert response.status_code == 200
    arena = response.get_json()["arena"]
    assert arena["incoming"] == 100
    assert arena["active_counters"] == 20
    assert arena["service_speed"] == 150
