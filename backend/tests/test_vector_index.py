from pathlib import Path
from typing import Any

from app.schemas.document import DocumentSegment
from app.services import vector_index


class FakeModel:
    """Remplace le modèle lourd par des vecteurs déterministes dans les tests."""

    def encode(self, texts, **kwargs):
        assert kwargs["normalize_embeddings"] is True
        return FakeArray([[float(index)] for index, _ in enumerate(texts)])


class FakeArray(list):
    def tolist(self):
        return list(self)


class FakeCollection:
    """Imite seulement les opérations Chroma utilisées par le service."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.query_arguments: dict[str, Any] | None = None

    @staticmethod
    def _matches(metadata: dict[str, Any], where: dict[str, Any]) -> bool:
        return all(
            metadata.get(key) == value
            for clause in where["$and"]
            for key, value in clause.items()
        )

    def get(self, where, include):
        return {
            "ids": [
                segment_id
                for segment_id, record in self.records.items()
                if self._matches(record["metadata"], where)
            ]
        }

    def upsert(self, ids, embeddings, documents, metadatas):
        for segment_id, embedding, document, metadata in zip(
            ids, embeddings, documents, metadatas, strict=True
        ):
            self.records[segment_id] = {
                "embedding": embedding,
                "document": document,
                "metadata": metadata,
            }

    def delete(self, ids=None, where=None):
        to_delete = set(ids or [])
        if where:
            to_delete.update(
                segment_id
                for segment_id, record in self.records.items()
                if self._matches(record["metadata"], where)
            )
        for segment_id in to_delete:
            self.records.pop(segment_id, None)

    def query(self, **kwargs):
        self.query_arguments = kwargs
        return {
            "ids": [["segment-1"]],
            "documents": [["texte"]],
            "metadatas": [[{"owner_id": 999, "course_id": 4}]],
            "distances": [[0.1]],
        }


def test_index_replaces_stale_segments_without_touching_other_accounts(monkeypatch, tmp_path) -> None:
    collection = FakeCollection()
    collection.records = {
        "old-segment": {"metadata": {"owner_id": 1, "document_id": 2}},
        "other-owner": {"metadata": {"owner_id": 9, "document_id": 2}},
    }
    monkeypatch.setattr(vector_index, "_get_collection", lambda path: collection)
    monkeypatch.setattr(vector_index, "_get_model", lambda model_name: FakeModel())
    segment = DocumentSegment(
        id="2:page:1:0",
        document_id=2,
        course_id=4,
        location_type="page",
        location_number=1,
        position=0,
        content="contenu du cours",
    )

    vector_index.index_document_segments(
        [segment], 1, "pdf", Path(tmp_path / "chroma"), "modele-test"
    )

    assert "old-segment" not in collection.records
    assert "other-owner" in collection.records
    assert collection.records[segment.id]["metadata"]["owner_id"] == 1
    assert collection.records[segment.id]["metadata"]["file_format"] == "pdf"


def test_search_filters_by_owner_and_rejects_mismatched_metadata(monkeypatch, tmp_path) -> None:
    collection = FakeCollection()
    monkeypatch.setattr(vector_index, "_get_collection", lambda path: collection)
    monkeypatch.setattr(vector_index, "_get_model", lambda model_name: FakeModel())

    results = vector_index.search_document_segments(
        "requête", 1, 4, [7], 5, Path(tmp_path / "chroma"), "modele-test"
    )

    assert results == []
    assert collection.query_arguments["where"] == {
        "$and": [
            {"owner_id": 1},
            {"course_id": 4},
            {"document_id": {"$in": [7]}},
        ]
    }


def test_delete_removes_only_the_requested_owner_document(monkeypatch, tmp_path) -> None:
    collection = FakeCollection()
    collection.records = {
        "owned": {"metadata": {"owner_id": 1, "document_id": 2}},
        "other-owner": {"metadata": {"owner_id": 9, "document_id": 2}},
    }
    monkeypatch.setattr(vector_index, "_get_collection", lambda path: collection)

    vector_index.delete_document_segments(2, 1, Path(tmp_path / "chroma"))

    assert "owned" not in collection.records
    assert "other-owner" in collection.records
