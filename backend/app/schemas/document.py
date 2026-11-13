from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    """Données publiques d'un document, sans exposer son chemin de stockage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    original_name: str
    file_format: Literal["pdf", "docx", "pptx", "txt"]
    unit_type: Literal["page", "slide", "paragraph", "line"]
    unit_count: int | None
    status: Literal["pending_indexing", "ocr_required", "no_text"]
    created_at: datetime


class DocumentSegment(BaseModel):
    """Passage référencé selon la structure propre à son format."""

    id: str
    document_id: int
    course_id: int
    location_type: Literal["page", "slide", "paragraph", "line"]
    location_number: int
    position: int
    content: str
