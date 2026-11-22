# Smart Queue Tickets

Smart Queue Tickets is a complete local-first queue management system built for clinics, hospitals, banks, universities, and service centers.

The application runs fully offline after package installation and includes:

- Customer Portal
- Receptionist Dashboard
- Staff Dashboard
- Public Queue Display
- Manager/Admin Analytics Dashboard
- Reports (CSV, Excel, PDF)
- QR and PDF ticket generation
- Role-based authentication with bcrypt
- SQLite persistence with SQLAlchemy
- Live demo/simulation mode

## Technology Stack

- Python 3.11+
- Streamlit
- SQLite + SQLAlchemy
- Pydantic
- Pandas + NumPy + Plotly
- qrcode + Pillow + ReportLab
- bcrypt
- Faker
- openpyxl
- pyttsx3
- pytest

## Project Structure

```
app.py
config.py
requirements.txt
database/
core/
modules/
services/
components/
assets/
data/
tests/
```

## Installation

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
streamlit run app.py
```

The database is created automatically at first launch (`data/smart_queue.db`) and seeded with demo data.

## Demo Accounts

- Admin: `admin` / `admin123`
- Manager: `manager` / `manager123`
- Receptionist: `reception` / `reception123`
- Staff: `staff` / `staff123`

## Testing

Run tests with:

```bash
pytest -q
```

## Notes

- This is a local hackathon project and does not use cloud services.
- All analytics are calculated from local SQLite records.