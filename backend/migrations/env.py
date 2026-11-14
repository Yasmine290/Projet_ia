from alembic import context

from app.db.database import get_engine
from app.models import Course, Document, LoginSession, StudyGuide, User
from app.models.base import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Applique les migrations à la même base que celle utilisée par l'API."""
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Les migrations hors ligne ne sont pas configurées.")
else:
    run_migrations_online()
