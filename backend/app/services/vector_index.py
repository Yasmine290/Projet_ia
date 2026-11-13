from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.document import DocumentSegment

COLLECTION_NAME = "studyai_segments_v1"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
INDEX_BATCH_SIZE = 64
EMBEDDING_BATCH_SIZE = 16
MAX_SEQUENCE_LENGTH = 256


class VectorIndexError(RuntimeError):
    """Erreur de persistance vectorielle pouvant être signalée par l'API."""


@lru_cache
def _get_collection(path: str) -> Any:
    """Ouvre la collection persistante locale, créée avec une distance cosine."""
    import chromadb

    client = chromadb.PersistentClient(
        path=path,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


@lru_cache
def _get_model(model_name: str) -> Any:
    """Charge le modèle seulement à la première demande d'indexation ou recherche."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    # L'architecture accepte 512 positions ; 256 limite la troncature des passages.
    model.max_seq_length = MAX_SEQUENCE_LENGTH
    return model


def _embed(texts: list[str], model_name: str) -> list[list[float]]:
    """Encode passages et requêtes avec le même modèle et une norme unitaire."""
    embeddings = _get_model(model_name).encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def index_document_segments(
    segments: list[DocumentSegment],
    owner_id: int,
    file_format: str,
    chroma_path: Path,
    model_name: str = EMBEDDING_MODEL,
) -> None:
    """Enregistre les passages et retire les anciens passages devenus obsolètes."""
    if not segments:
        raise ValueError("Un document doit contenir au moins un passage à indexer.")

    collection = _get_collection(str(chroma_path))
    scope = {"$and": [{"owner_id": owner_id}, {"document_id": segments[0].document_id}]}
    old_ids = set(collection.get(where=scope, include=[])["ids"])
    new_ids = [segment.id for segment in segments]
    metadatas = [
        {
            "owner_id": owner_id,
            "course_id": segment.course_id,
            "document_id": segment.document_id,
            "file_format": file_format,
            "location_type": segment.location_type,
            "location_number": segment.location_number,
            "position": segment.position,
        }
        for segment in segments
    ]

    # L'upsert précède le nettoyage pour ne pas effacer l'ancienne version si l'encodage échoue.
    # Traiter par lots borne la mémoire pour les documents contenant beaucoup de texte.
    for start in range(0, len(segments), INDEX_BATCH_SIZE):
        end = start + INDEX_BATCH_SIZE
        batch = segments[start:end]
        collection.upsert(
            ids=new_ids[start:end],
            embeddings=_embed([segment.content for segment in batch], model_name),
            documents=[segment.content for segment in batch],
            metadatas=metadatas[start:end],
        )
    stale_ids = old_ids - set(new_ids)
    if stale_ids:
        # Chroma supprime selon les identifiants OU le filtre ; ces IDs ont déjà été filtrés.
        collection.delete(ids=list(stale_ids))


def search_document_segments(
    query: str,
    owner_id: int,
    course_id: int,
    document_ids: list[int],
    limit: int,
    chroma_path: Path,
    model_name: str = EMBEDDING_MODEL,
) -> list[dict[str, Any]]:
    """Recherche uniquement dans les passages du propriétaire et du cours demandés."""
    if not document_ids:
        return []
    collection = _get_collection(str(chroma_path))
    result = collection.query(
        query_embeddings=_embed([query], model_name),
        n_results=limit,
        where={
            "$and": [
                {"owner_id": owner_id},
                {"course_id": course_id},
                {"document_id": {"$in": document_ids}},
            ]
        },
        include=["documents", "metadatas", "distances"],
    )

    matches: list[dict[str, Any]] = []
    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]
    for segment_id, content, metadata, distance in zip(
        ids, documents, metadatas, distances, strict=True
    ):
        if metadata is None or content is None or distance is None:
            continue
        # Défense en profondeur : ne pas faire confiance aux métadonnées retournées seules.
        if metadata.get("owner_id") != owner_id or metadata.get("course_id") != course_id:
            continue
        matches.append(
            {
                "id": segment_id,
                "content": content,
                "metadata": metadata,
                "distance": float(distance),
            }
        )
    return matches


def delete_document_segments(document_id: int, owner_id: int, chroma_path: Path) -> None:
    """Supprime les vecteurs du document sans toucher aux autres comptes."""
    import chromadb

    try:
        collection = _get_collection(str(chroma_path))
        collection.delete(
            where={
                "$and": [
                    {"owner_id": owner_id},
                    {"document_id": document_id},
                ]
            }
        )
    except (chromadb.errors.ChromaError, OSError) as exc:
        raise VectorIndexError("Impossible de supprimer les vecteurs du document.") from exc
