import unicodedata
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Path as RoutePath, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.courses import find_course
from app.core.config import Settings, get_settings
from app.db.database import get_session
from app.models.document import Document
from app.models.course import Course
from app.models.user import User
from app.schemas.answer import AnswerCitation, AnswerRequest, AnswerResponse
from app.schemas.document import (
    DocumentRead,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentSearchResult,
    DocumentSegment,
)
from app.services.auth import get_current_user
from app.services.documents import extract_segments, resolve_document_path, store_document
from app.services.ollama import OllamaService, get_ollama_service
from app.services.vector_index import (
    VectorIndexError,
    delete_document_segments,
    index_document_segments,
    search_document_segments,
)

router = APIRouter(prefix="/api", tags=["documents"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
UserDep = Annotated[User, Depends(get_current_user)]
OllamaDep = Annotated[OllamaService, Depends(get_ollama_service)]

SUMMARY_QUERY_INTENTS = (
    "de quoi parle",
    "parle de quoi",
    "de quoi traite",
    "traite de quoi",
    "resume",
    "synthese",
    "idee principale",
    "theme principal",
    "sujets abordes",
    "vue d'ensemble",
)


def _retrieval_query(query: str) -> str:
    """Élargit les recherches de synthèse vers les thèmes et idées principales."""
    normalized = unicodedata.normalize("NFKD", query.casefold())
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    if any(intent in normalized for intent in SUMMARY_QUERY_INTENTS):
        return f"{query} thèmes principaux idées clés notions abordées"
    return query


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
    """Extrait les passages avec leurs repères sans modifier l'index."""
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


@router.post("/documents/{document_id}/index", response_model=DocumentRead)
def index_document(
    document_id: int, session: SessionDep, settings: SettingsDep, user: UserDep
) -> Document:
    """Extrait et indexe explicitement un document avec ses repères de source."""
    document = find_document(session, document_id, user.id)
    path = resolve_document_path(settings.resolved_upload_dir, document.storage_name)
    segments = extract_segments(
        path,
        document.file_format,
        document.id,
        document.course_id,
        settings.chunk_size,
        settings.max_archive_entries,
        settings.max_expanded_bytes,
    )
    # Un nouvel essai ne doit pas exposer un index partiellement rafraîchi.
    document.status = "pending_indexing"
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    index_document_segments(
        segments,
        user.id,
        document.file_format,
        settings.resolved_chroma_path,
    )
    document.status = "indexed"
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(document)
    return document


@router.post(
    "/courses/{course_id}/search",
    response_model=DocumentSearchResponse,
)
def search_course_documents(
    course_id: int,
    request: DocumentSearchRequest,
    session: SessionDep,
    settings: SettingsDep,
    user: UserDep,
) -> DocumentSearchResponse:
    """Recherche des passages en limitant la requête au cours du compte connecté."""
    results = _search_course_segments(
        session,
        settings,
        user.id,
        course_id,
        request.query,
        request.limit,
    )
    return DocumentSearchResponse(query=request.query, results=results)


def _search_course_segments(
    session: Session,
    settings: Settings,
    owner_id: int,
    course_id: int,
    query: str,
    limit: int,
) -> list[DocumentSearchResult]:
    """Recherche les passages d'un cours après vérification de son propriétaire."""
    find_course(session, course_id, owner_id)
    documents = {
        document.id: document
        for document in session.scalars(
            select(Document).where(
                Document.course_id == course_id,
                Document.status == "indexed",
            )
        ).all()
    }
    if not documents:
        return []

    matches = search_document_segments(
        query,
        owner_id,
        course_id,
        list(documents),
        limit,
        settings.resolved_chroma_path,
    )

    results: list[DocumentSearchResult] = []
    for match in matches:
        metadata = match["metadata"]
        document = documents.get(metadata["document_id"])
        if document is None:
            # Un index résiduel après une suppression ne doit jamais être renvoyé.
            continue
        results.append(
            DocumentSearchResult(
                segment=DocumentSegment(
                    id=match["id"],
                    document_id=document.id,
                    course_id=course_id,
                    location_type=metadata["location_type"],
                    location_number=metadata["location_number"],
                    position=metadata["position"],
                    content=match["content"],
                ),
                document_name=document.original_name,
                file_format=document.file_format,
                distance=match["distance"],
            )
        )
    return results


@router.post(
    "/courses/{course_id}/ask",
    response_model=AnswerResponse,
)
async def ask_course(
    course_id: int,
    request: AnswerRequest,
    session: SessionDep,
    settings: SettingsDep,
    user: UserDep,
    ollama: OllamaDep,
) -> AnswerResponse:
    """Répond à une question à partir des passages accessibles du cours."""
    results = await run_in_threadpool(
        _search_course_segments,
        session,
        settings,
        user.id,
        course_id,
        _retrieval_query(request.query),
        request.limit,
    )
    if not results:
        return AnswerResponse(
            query=request.query,
            answer="Aucun passage pertinent n'a été retrouvé dans les documents indexés du cours.",
            citations=[],
        )

    generated = await ollama.generate_answer(request.query, results)
    sources_by_id = {
        f"S{index}": source for index, source in enumerate(results, start=1)
    }
    citations = [
        AnswerCitation(
            citation_id=citation_id,
            document_name=sources_by_id[citation_id].document_name,
            file_format=sources_by_id[citation_id].file_format,
            segment=sources_by_id[citation_id].segment,
        )
        for citation_id in generated.citation_ids
    ]
    return AnswerResponse(
        query=request.query,
        answer=generated.answer,
        citations=citations,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, session: SessionDep, settings: SettingsDep, user: UserDep) -> Response:
    """Supprime l'index, le document et son fichier avec gestion des échecs."""
    document = find_document(session, document_id, user.id)
    path = resolve_document_path(settings.resolved_upload_dir, document.storage_name)
    if not path.is_file():
        raise HTTPException(
            status_code=500, detail="Impossible de déplacer le fichier du document pour suppression."
        )
    temporary_path = path.with_name(f"{path.name}.{uuid4().hex}.deleting")

    # Les recherches ignorent le document pendant le nettoyage de son index.
    document.status = "pending_indexing"
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    try:
        delete_document_segments(document.id, user.id, settings.resolved_chroma_path)
    except VectorIndexError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Document conservé en attente : impossible de supprimer son index local. "
                "Il reste masqué des recherches et peut être réindexé."
            ),
        ) from exc

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
