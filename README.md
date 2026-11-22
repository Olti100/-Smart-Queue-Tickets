# Smart Queue Tickets

Smart Queue Tickets is a local-first queue management app for hackathon demos.

This version is optimized for speed and reliability, with a Flask UI and SQLite backend.

## Included Modules

- Customer Portal: generate and track tickets, submit feedback
- Receptionist Dashboard: register walk-ins, search, cancel, transfer
- Staff Dashboard: call next, start/complete service, skip/recall, pause/resume counter
- Public Queue Display: live serving and waiting lists with auto-refresh
- Manager Dashboard: KPI summary and peak-hour insights

## Technology

- Python 3.11+
- Flask
- SQLite + SQLAlchemy
- Pydantic (config fallback supported)
- Pandas + NumPy
- bcrypt
- pytest

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

The database is auto-created at first run in `data/smart_queue.db` with seeded demo data.

## Demo Accounts

- admin / admin123
- manager / manager123
- reception / reception123
- staff / staff123

## Customer Accounts

Customers can create a local account from `/register` and sign in at `/login`. New accounts receive the `CUSTOMER` role and can still use the public ticket portal.

## Run Tests

```bash
pytest -q
```

## Notes

- Fully local, no cloud services.
- All queue metrics and dashboards read from SQLite records.