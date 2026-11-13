from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentRead(BaseModel):
    """Données publiques d'un document, sans exposer son chemin de stockage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    original_name: str
    file_format: Literal["pdf", "docx", "pptx", "txt", "doc", "ppt"]
    unit_type: Literal["page", "slide", "paragraph", "line"]
    unit_count: int | None
    status: Literal["pending_indexing", "indexed", "ocr_required", "no_text"]
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


class DocumentSearchRequest(BaseModel):
    """Requête bornée pour éviter des calculs d'embeddings sans limite."""

    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        """Refuse une requête qui ne contient que des espaces."""
        value = value.strip()
        if not value:
            raise ValueError("La recherche ne peut pas être vide.")
        return value


class DocumentSearchResult(BaseModel):
    """Passage trouvé avec son document d'origine et sa distance cosine."""

    segment: DocumentSegment
    document_name: str
    file_format: Literal["pdf", "docx", "pptx", "txt", "doc", "ppt"]
    distance: float


class DocumentSearchResponse(BaseModel):
    """Résultats de recherche sémantique dans un cours."""

    query: str
    results: list[DocumentSearchResult]
