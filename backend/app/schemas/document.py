from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    """Données publiques d'un document, sans exposer son chemin de stockage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    original_name: str
    page_count: int
    status: Literal["pending_indexing", "ocr_required"]
    created_at: datetime


class DocumentSegment(BaseModel):
    """Passage associé à son document et à sa page d'origine (numérotée dès 1)."""

    id: str
    document_id: int
    course_id: int
    page: int
    position: int
    content: str
