from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Regroupe les tables suivies par SQLAlchemy et Alembic."""
