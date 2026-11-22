# Smart Queue Tickets

Smart Queue Tickets is a local-first business queue platform for clinics, banks, government offices, universities, service centers, and other organizations.

Businesses can register staff teams, issue digital queue tickets, operate reception and service counters, monitor live waiting-room activity, and analyze peak customer hours. Customers can register locally, generate or track their ticket, view wait estimates, and submit feedback.

This version is optimized for speed and reliability, with a Flask UI and SQLite backend.

## Included Modules

- Business Accounts: register teams and secure staff/customer access by role
- Customer Portal: generate digital tickets, track queue position and waiting time, submit feedback
- Receptionist Dashboard: issue tickets to walk-ins, search customers, cancel or transfer tickets
- Staff Dashboard: call, serve, complete, recall, skip, and transfer issued tickets
- Public Queue Display: show live ticket calls and waiting-room activity
- Manager Dashboard: monitor operations and identify peak customer hours, demand, counter load, and department performance

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

## How the platform works

The app has two audiences:

1. **Businesses** register a manager workspace and use Reception, Staff, Analytics, Queue Arena, and Database tools.
2. **Customers** generate and track digital queue tickets, see their position and estimated wait, and submit feedback.

The Public Queue Display is a shared waiting-room view for both teams and customers.