from database.connection import get_session, init_database
from database.seed import seed_initial_data


def bootstrap_database() -> None:
    init_database()
    with get_session() as session:
        seed_initial_data(session)
