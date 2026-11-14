from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.answer import AnswerCitation

StudyGuideKind = Literal["short", "detailed", "sheet"]


class StudyGuideRequest(BaseModel):
    """Mode de génération choisi pour un document indexé."""

    kind: StudyGuideKind = "short"


class StudyGuideSection(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2500)


class StudyGuideFlashcard(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=1200)


class GeneratedStudyGuide(BaseModel):
    """Contenu structuré produit à partir des passages retrouvés."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    intro: str = Field(min_length=1, max_length=1500)
    sections: list[StudyGuideSection] = Field(max_length=6)
    flashcards: list[StudyGuideFlashcard] = Field(max_length=5)
    citation_ids: list[str] = Field(min_length=1, max_length=5)

    @field_validator("citation_ids")
    @classmethod
    def require_unique_citations(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Les références de citation doivent être uniques.")
        return value


class StudyGuideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    kind: StudyGuideKind
    title: str
    intro: str
    sections: list[StudyGuideSection]
    flashcards: list[StudyGuideFlashcard]
    citations: list[AnswerCitation]
    created_at: datetime
