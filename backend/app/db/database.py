from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings


def create_database_engine(database_url: str) -> Engine:
    """Construit une connexion SQLite et active ses contraintes de clés étrangères."""
    url = make_url(database_url)
    if url.drivername != "sqlite":
        raise ValueError("Seule une base SQLite locale est prise en charge.")
    if url.database and url.database != ":memory:":
        path = Path(url.database)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        url = url.set(database=str(path.resolve()))

    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:
        # SQLite ne vérifie pas les clés étrangères tant que ce pragma n'est pas activé.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    return create_database_engine(get_settings().database_url)


def get_session() -> Iterator[Session]:
    """Ouvre une session par requête et la ferme après la réponse."""
    with Session(get_engine()) as session:
        yield session
