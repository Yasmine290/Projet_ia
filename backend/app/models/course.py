from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Course(Base):
    """Cours du prototype local, sans authentification."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # L'heure UTC permet de comparer les dates sans dépendre du fuseau local.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
