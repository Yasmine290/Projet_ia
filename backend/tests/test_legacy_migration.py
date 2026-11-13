import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.claim_courses import main as claim_courses
from app.core.config import BACKEND_DIR, get_settings
from app.db.database import get_engine
from app.main import app


def test_legacy_data_is_preserved_and_requires_explicit_claim(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Un cours antérieur reste privé jusqu'à son attribution volontaire."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'old.sqlite').as_posix()}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    get_engine.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    try:
        command.upgrade(config, "0001")
        engine = get_engine()
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO courses (id, title, description, created_at) "
                "VALUES (1, 'Ancien cours', '', '2026-01-01 00:00:00')"
            ))
            connection.execute(text(
                "INSERT INTO documents (id, course_id, original_name, storage_name, "
                "page_count, status, created_at) VALUES "
                "(1, 1, 'ancien.pdf', 'ancien.pdf', 1, 'pending_indexing', '2026-01-01 00:00:00')"
            ))
        command.upgrade(config, "head")
        with TestClient(app) as client:
            credentials = {"username": "alice", "password": "mot-de-passe-test"}
            assert client.post("/api/auth/register", json=credentials).status_code == 201
            token = client.post("/api/auth/login", json=credentials).json()["access_token"]
            client.headers["Authorization"] = f"Bearer {token}"
            assert client.get("/api/courses").json() == []
            assert client.get("/api/documents/1").status_code == 404
            monkeypatch.setattr(sys, "argv", ["claim_courses", "alice"])
            with pytest.raises(SystemExit):
                claim_courses()
            assert client.get("/api/courses").json() == []
            monkeypatch.setattr(sys, "argv", ["claim_courses", "alice", "--confirm"])
            claim_courses()
            assert "1 cours" in capsys.readouterr().out
            assert client.get("/api/courses/1").json()["title"] == "Ancien cours"
            assert client.get("/api/documents/1").json()["original_name"] == "ancien.pdf"
    finally:
        get_engine().dispose()
        get_engine.cache_clear()
        get_settings.cache_clear()
