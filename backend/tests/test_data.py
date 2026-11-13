from pathlib import Path

import pymupdf
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings
from app.db.database import get_engine
from app.main import app
from app.models.course import Course


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Utilise une base migrée et un dossier de fichiers isolés pour chaque test."""
    database_path = tmp_path / "test.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4096")
    get_settings.cache_clear()
    get_engine.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    engine = get_engine()
    with TestClient(app) as client:
        yield client, tmp_path, engine
    engine.dispose()
    get_engine.cache_clear()
    get_settings.cache_clear()


def pdf_bytes(with_text: bool = True, password: bool = False) -> bytes:
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        if with_text:
            page.insert_text((72, 72), "Cours de test")
        if password:
            return pdf.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
        return pdf.tobytes()


def test_courses_are_persisted_and_validated(api) -> None:
    client, _, engine = api
    assert client.post("/api/courses", json={"title": "  "}).status_code == 422
    response = client.post("/api/courses", json={"title": " Math ", "description": "Notes"})
    assert response.status_code == 201
    course_id = response.json()["id"]
    assert response.json()["title"] == "Math"
    assert client.get("/api/courses").json()[0]["id"] == course_id
    assert client.patch(f"/api/courses/{course_id}", json={"title": None}).status_code == 422
    assert client.patch(f"/api/courses/{course_id}", json={"title": "Physique"}).json()["title"] == "Physique"
    with Session(engine) as session:
        assert session.scalar(select(Course).where(Course.id == course_id)).title == "Physique"
    assert client.delete(f"/api/courses/{course_id}").status_code == 204
    assert client.get(f"/api/courses/{course_id}").status_code == 404


def test_pdf_lifecycle_and_course_deletion_protection(api) -> None:
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Test"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("../../notes.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["original_name"] == "notes.pdf"
    assert document["page_count"] == 1
    assert document["status"] == "pending_indexing"
    assert "storage_name" not in document
    files = list((tmp_path / "uploads").iterdir())
    assert len(files) == 1 and files[0].name != "notes.pdf"
    assert client.get(f"/api/courses/{course_id}/documents").json() == [document]
    assert client.get(f"/api/documents/{document['id']}").json() == document
    assert client.delete(f"/api/courses/{course_id}").status_code == 409
    assert client.delete(f"/api/documents/{document['id']}").status_code == 204
    assert not files[0].exists()
    assert client.delete(f"/api/courses/{course_id}").status_code == 204


def test_pdf_rejections_and_ocr_status(api) -> None:
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Test"}).json()["id"]
    url = f"/api/courses/{course_id}/documents"
    assert client.post(url, files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}).status_code == 415
    assert client.post(url, files={"file": ("test.pdf", pdf_bytes(password=True), "application/pdf")}).status_code == 422
    assert client.post(url, files={"file": ("large.pdf", b"x" * 4097, "application/pdf")}).status_code == 413
    assert list((tmp_path / "uploads").iterdir()) == []
    response = client.post(url, files={"file": ("scan.pdf", pdf_bytes(False), "application/pdf")})
    assert response.status_code == 201
    assert response.json()["status"] == "ocr_required"
    assert client.post("/api/courses/999/documents", files={"file": ("test.pdf", pdf_bytes(), "application/pdf")}).status_code == 404


def test_failed_delete_restores_pdf(api, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un échec de transaction ne doit pas faire disparaître le PDF."""
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Test"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.pdf", pdf_bytes(), "application/pdf")},
    )
    document_id = response.json()["id"]
    original_path = next((tmp_path / "uploads").iterdir())

    def fail_commit(self: Session) -> None:
        raise RuntimeError("Échec simulé de la transaction")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="Échec simulé"):
            client.delete(f"/api/documents/{document_id}")

    assert original_path.exists()
    assert client.get(f"/api/documents/{document_id}").status_code == 200


def test_extract_document_segments_with_page_references(api) -> None:
    """Les passages conservent leurs références et leur ordre entre deux lectures."""
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours"}).json()["id"]
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "Texte de la premiere page.")
        pdf.new_page().insert_text((72, 72), "Texte de la deuxieme page.")
        content = pdf.tobytes()
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("cours.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]
    result = client.get(f"/api/documents/{document_id}/segments")
    assert result.status_code == 200
    segments = result.json()
    assert [segment["page"] for segment in segments] == [1, 2]
    assert [segment["content"] for segment in segments] == [
        "Texte de la premiere page.",
        "Texte de la deuxieme page.",
    ]
    assert all(segment["document_id"] == document_id for segment in segments)
    assert all(segment["course_id"] == course_id for segment in segments)
    assert len({segment["id"] for segment in segments}) == 2
    assert client.get(f"/api/documents/{document_id}/segments").json() == segments


def test_extract_segments_reports_missing_text_and_missing_document(api) -> None:
    """Un PDF sans texte ne doit pas produire une liste de passages trompeuse."""
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("scan.pdf", pdf_bytes(False), "application/pdf")},
    )
    result = client.get(f"/api/documents/{response.json()['id']}/segments")
    assert result.status_code == 422
    assert "OCR" in result.json()["detail"]
    assert client.get("/api/documents/999/segments").status_code == 404


def test_extract_segments_reports_missing_file(api) -> None:
    """Un fichier disparu ne doit pas être présenté comme un document indexable."""
    client, tmp_path, _ = api
    course_id = client.post("/api/courses", json={"title": "Cours"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("cours.pdf", pdf_bytes(), "application/pdf")},
    )
    next((tmp_path / "uploads").iterdir()).unlink()
    result = client.get(f"/api/documents/{response.json()['id']}/segments")
    assert result.status_code == 422
    assert "inaccessible" in result.json()["detail"]
