from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.courses import find_course
from app.core.config import Settings, get_settings
from app.db.database import get_session
from app.models.document import Document
from app.schemas.document import DocumentRead, DocumentSegment
from app.services.documents import extract_segments, resolve_document_path, store_pdf

router = APIRouter(prefix="/api", tags=["documents"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def find_document(session: Session, document_id: int) -> Document:
    """Recherche les métadonnées d'un document ou renvoie une erreur 404."""
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return document


@router.post("/courses/{course_id}/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    course_id: int, file: UploadFile, session: SessionDep, settings: SettingsDep
) -> Document:
    """Stocke un PDF valide puis associe ses métadonnées au cours choisi."""
    find_course(session, course_id)
    name, page_count, processing_status = await store_pdf(
        file, settings.resolved_upload_dir, settings.max_upload_bytes
    )
    # Le nom original sert uniquement à l'affichage, jamais à construire un chemin.
    original_name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1][:255]
    document = Document(
        course_id=course_id,
        original_name=original_name,
        storage_name=name,
        page_count=page_count,
        status=processing_status,
    )
    try:
        session.add(document)
        session.commit()
    except Exception:
        # Si SQLite refuse l'enregistrement, le PDF ne doit pas rester orphelin.
        session.rollback()
        (settings.resolved_upload_dir / name).unlink(missing_ok=True)
        raise
    session.refresh(document)
    return document


@router.get("/courses/{course_id}/documents", response_model=list[DocumentRead])
def list_documents(course_id: int, session: SessionDep) -> list[Document]:
    """Retourne les documents associés à un cours existant."""
    find_course(session, course_id)
    return list(
        session.scalars(
            select(Document).where(Document.course_id == course_id).order_by(Document.id)
        ).all()
    )


@router.get("/documents/{document_id}", response_model=DocumentRead)
def read_document(document_id: int, session: SessionDep) -> Document:
    """Retourne les métadonnées publiques et l'état d'un document."""
    return find_document(session, document_id)


@router.get("/documents/{document_id}/segments", response_model=list[DocumentSegment])
def read_document_segments(
    document_id: int, session: SessionDep, settings: SettingsDep
) -> list[DocumentSegment]:
    """Extrait les passages avec leurs pages pour préparer une future indexation."""
    document = find_document(session, document_id)
    path = resolve_document_path(settings.resolved_upload_dir, document.storage_name)
    return extract_segments(
        path, document.id, document.course_id, settings.chunk_size
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, session: SessionDep, settings: SettingsDep) -> Response:
    """Supprime un document et son fichier avec restauration en cas d'échec SQLite."""
    document = find_document(session, document_id)
    path = resolve_document_path(settings.resolved_upload_dir, document.storage_name)
    temporary_path = path.with_name(f"{path.name}.{uuid4().hex}.deleting")
    try:
        # Conserver le fichier jusqu'à la confirmation de la transaction SQLite.
        path.rename(temporary_path)
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="Impossible de déplacer le fichier du document pour suppression."
        ) from exc
    try:
        session.delete(document)
        session.commit()
    except Exception:
        session.rollback()
        temporary_path.rename(path)
        raise
    try:
        temporary_path.unlink()
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Document supprimé de la base, mais le fichier temporaire n'a pas pu être supprimé.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
