from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Path as RoutePath, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.courses import find_course
from app.core.config import Settings, get_settings
from app.db.database import get_session
from app.models.document import Document
from app.models.course import Course
from app.models.user import User
from app.schemas.document import DocumentRead, DocumentSegment
from app.services.auth import get_current_user
from app.services.documents import extract_segments, resolve_document_path, store_document

router = APIRouter(prefix="/api", tags=["documents"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
UserDep = Annotated[User, Depends(get_current_user)]


def find_document(session: Session, document_id: int, owner_id: int) -> Document:
    """Un document n'est accessible qu'au propriétaire de son cours."""
    document = session.scalar(
        select(Document).join(Course).where(
            Document.id == document_id, Course.owner_id == owner_id
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return document


@router.post("/courses/{course_id}/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    course_id: Annotated[int, RoutePath(alias="course_id")],
    file: Annotated[UploadFile, File(alias="file")],
    session: SessionDep,
    settings: SettingsDep,
    user: UserDep,
) -> Document:
    """Stocke un document pris en charge puis associe ses métadonnées au cours."""
    find_course(session, course_id, user.id)
    name, file_format, unit_type, unit_count, processing_status = await store_document(
        file,
        settings.resolved_upload_dir,
        settings.max_upload_bytes,
        settings.max_archive_entries,
        settings.max_expanded_bytes,
        settings.libreoffice_path,
        settings.legacy_conversion_timeout_seconds,
    )
    # Le nom original sert uniquement à l'affichage, jamais à construire un chemin.
    original_name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1][:255]
    document = Document(
        course_id=course_id,
        original_name=original_name,
        storage_name=name,
        file_format=file_format,
        unit_type=unit_type,
        unit_count=unit_count,
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
def list_documents(course_id: int, session: SessionDep, user: UserDep) -> list[Document]:
    """Retourne les documents associés à un cours existant."""
    find_course(session, course_id, user.id)
    return list(
        session.scalars(
            select(Document).where(Document.course_id == course_id).order_by(Document.id)
        ).all()
    )


@router.get("/documents/{document_id}", response_model=DocumentRead)
def read_document(document_id: int, session: SessionDep, user: UserDep) -> Document:
    """Retourne les métadonnées publiques et l'état d'un document."""
    return find_document(session, document_id, user.id)


@router.get("/documents/{document_id}/segments", response_model=list[DocumentSegment])
def read_document_segments(
    document_id: int, session: SessionDep, settings: SettingsDep, user: UserDep
) -> list[DocumentSegment]:
    """Extrait les passages avec leurs repères pour préparer une future indexation."""
    document = find_document(session, document_id, user.id)
    path = resolve_document_path(settings.resolved_upload_dir, document.storage_name)
    return extract_segments(
        path,
        document.file_format,
        document.id,
        document.course_id,
        settings.chunk_size,
        settings.max_archive_entries,
        settings.max_expanded_bytes,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, session: SessionDep, settings: SettingsDep, user: UserDep) -> Response:
    """Supprime un document et son fichier avec restauration en cas d'échec SQLite."""
    document = find_document(session, document_id, user.id)
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
