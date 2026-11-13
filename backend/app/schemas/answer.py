from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.document import DocumentSegment


class AnswerRequest(BaseModel):
    """Question bornée et nombre maximal de passages à fournir au modèle."""

    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=5)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        """Refuse une question qui ne contient que des espaces."""
        value = value.strip()
        if not value:
            raise ValueError("La question ne peut pas être vide.")
        return value


class GeneratedAnswer(BaseModel):
    """Réponse structurée produite par Ollama avant ajout des sources publiques."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=7900)
    citation_ids: list[str] = Field(max_length=5)

    @field_validator("answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("La réponse ne peut pas être vide.")
        return value

    @field_validator("citation_ids")
    @classmethod
    def require_unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Les références de citation doivent être uniques.")
        return value


class AnswerCitation(BaseModel):
    """Source vérifiée associée à un marqueur de citation dans la réponse."""

    citation_id: str
    document_name: str
    file_format: Literal["pdf", "docx", "pptx", "txt", "doc", "ppt"]
    segment: DocumentSegment


class AnswerResponse(BaseModel):
    """Réponse à une question de cours et passages qui l'étayent."""

    query: str
    answer: str
    citations: list[AnswerCitation]
