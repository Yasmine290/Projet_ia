from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.course import utc_now


class Document(Base):
    """Métadonnées d'un document ; son contenu reste sur le disque local."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # La clé étrangère relie le document à un cours existant.
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Le nom original est affiché ; le nom de stockage est généré par l'application.
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    # La nature des unités dépend du format : pages, diapositives, paragraphes ou lignes.
    file_format: Mapped[str] = mapped_column(String(10), nullable=False, default="pdf")
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False, default="page")
    unit_count: Mapped[int | None] = mapped_column(nullable=True)
    # OCR uniquement pour les PDF scannés ; les autres formats peuvent simplement être vides.
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
