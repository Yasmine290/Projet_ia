import pytest

from app.api import documents as document_api
from app.services.vector_index import VectorIndexError
from test_data import api


def test_index_search_and_delete_use_the_authenticated_owner(api, monkeypatch) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Histoire"}).json()["id"]
    uploaded = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.txt", b"Une lecon importante.", "text/plain")},
    )
    document = uploaded.json()
    calls = {}

    def fake_index(segments, owner_id, file_format, chroma_path):
        calls["index"] = (segments, owner_id, file_format)

    def fake_search(query, owner_id, requested_course, document_ids, limit, chroma_path):
        calls["search"] = (query, owner_id, requested_course, document_ids, limit)
        return [
            {
                "id": f"{document['id']}:line:1:0",
                "content": "Une lecon importante.",
                "metadata": {
                    "document_id": document["id"],
                    "location_type": "line",
                    "location_number": 1,
                    "position": 0,
                },
                "distance": 0.12,
            }
        ]

    deleted = []
    monkeypatch.setattr(document_api, "index_document_segments", fake_index)
    monkeypatch.setattr(document_api, "search_document_segments", fake_search)
    monkeypatch.setattr(
        document_api,
        "delete_document_segments",
        lambda document_id, owner_id, chroma_path: deleted.append((document_id, owner_id)),
    )

    indexed = client.post(f"/api/documents/{document['id']}/index")
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["status"] == "indexed"
    assert calls["index"][1:] == (1, "txt")

    search = client.post(
        f"/api/courses/{course_id}/search",
        json={"query": "leçon", "limit": 3},
    )
    assert search.status_code == 200, search.text
    result = search.json()["results"][0]
    assert calls["search"] == ("leçon", 1, course_id, [document["id"]], 3)
    assert result["segment"]["location_type"] == "line"
    assert result["document_name"] == "notes.txt"
    assert result["distance"] == 0.12

    assert client.delete(f"/api/documents/{document['id']}").status_code == 204
    assert deleted == [(document["id"], 1)]


def test_search_rejects_another_accounts_course_before_vector_query(api, monkeypatch) -> None:
    client, _, _ = api
    own_course_id = client.post("/api/courses", json={"title": "Mon cours"}).json()["id"]
    assert client.post(
        "/api/auth/register",
        json={"username": "autre_etudiant", "password": "un-autre-mot-de-passe"},
    ).status_code == 201
    other_token = client.post(
        "/api/auth/login",
        json={"username": "autre_etudiant", "password": "un-autre-mot-de-passe"},
    ).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {other_token}"
    called = False

    def unexpected_search(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(document_api, "search_document_segments", unexpected_search)
    response = client.post(
        f"/api/courses/{own_course_id}/search",
        json={"query": "cours"},
    )

    assert response.status_code == 404
    assert not called


def test_search_rejects_a_blank_query(api) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours"}).json()["id"]

    response = client.post(f"/api/courses/{course_id}/search", json={"query": "   "})

    assert response.status_code == 422


def test_search_skips_model_when_course_has_no_indexed_documents(api, monkeypatch) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours en attente"}).json()["id"]
    uploaded = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.txt", b"Texte pas encore indexe.", "text/plain")},
    )
    assert uploaded.json()["status"] == "pending_indexing"

    def unexpected_search(*args, **kwargs):
        pytest.fail("La recherche ne doit pas charger le modèle sans document indexé.")

    monkeypatch.setattr(document_api, "search_document_segments", unexpected_search)
    response = client.post(
        f"/api/courses/{course_id}/search",
        json={"query": "texte"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_failed_reindex_keeps_document_pending(api, monkeypatch) -> None:
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours"}).json()["id"]
    uploaded = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.txt", b"Un texte a indexer.", "text/plain")},
    )
    document_id = uploaded.json()["id"]

    def fail_index(*args, **kwargs):
        raise RuntimeError("Échec simulé de l'indexation")

    monkeypatch.setattr(document_api, "index_document_segments", fail_index)
    with pytest.raises(RuntimeError, match="Échec simulé"):
        client.post(f"/api/documents/{document_id}/index")

    assert client.get(f"/api/documents/{document_id}").json()["status"] == "pending_indexing"


def test_vector_cleanup_failure_preserves_document_and_file(api, monkeypatch) -> None:
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours"}).json()["id"]
    uploaded = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.txt", b"Texte a supprimer.", "text/plain")},
    )
    document_id = uploaded.json()["id"]
    stored_file = next((tmp_path / "uploads").iterdir())

    def fail_cleanup(document_id, owner_id, chroma_path):
        raise VectorIndexError("échec simulé de Chroma")

    monkeypatch.setattr(document_api, "delete_document_segments", fail_cleanup)
    response = client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 503
    assert "conservé en attente" in response.json()["detail"]
    assert stored_file.exists()
    assert client.get(f"/api/documents/{document_id}").json()["status"] == "pending_indexing"


def test_missing_file_does_not_delete_vector_index(api, monkeypatch) -> None:
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours"}).json()["id"]
    uploaded = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.txt", b"Texte.", "text/plain")},
    )
    document_id = uploaded.json()["id"]
    next((tmp_path / "uploads").iterdir()).unlink()
    calls = []
    monkeypatch.setattr(
        document_api,
        "delete_document_segments",
        lambda *args: calls.append(args),
    )

    response = client.delete(f"/api/documents/{document_id}")

    assert response.status_code == 500
    assert calls == []
    assert client.get(f"/api/documents/{document_id}").status_code == 200
