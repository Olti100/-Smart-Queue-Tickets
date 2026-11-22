from pathlib import Path

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:
    class BaseModel:  # type: ignore[override]
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, default_factory=None):  # type: ignore[misc]
        if default_factory is not None:
            return default_factory()
        return default


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "smart_queue.db"


class AppSettings(BaseModel):
    app_name: str = "Smart Queue Tickets"
    org_name: str = "Smart Queue Organization"
    db_url: str = Field(default_factory=lambda: f"sqlite:///{DB_PATH.as_posix()}")
    default_theme: str = "light"
    default_ticket_prefix: str = "A"
    wait_prediction_buffer: float = 1.15
    queue_refresh_seconds: int = 5


settings = AppSettings()
