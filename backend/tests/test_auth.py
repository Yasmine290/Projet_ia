import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import LoginSession, User
from app.services.auth import hash_token
from test_data import api, pdf_bytes


def register_and_login(client, username: str) -> str:
    credentials = {"username": username, "password": "mot-de-passe-test"}
    assert client.post("/api/auth/register", json=credentials).status_code == 201
    response = client.post("/api/auth/login", json=credentials)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["access_token"]


def test_registration_login_and_logout(api) -> None:
    """Les mots de passe et les jetons ne sont pas stockés en clair."""
    client, _, engine = api
    client.headers.pop("Authorization")
    assert client.get("/api/courses").status_code == 401
    response = client.post("/api/auth/register", json={
        "username": "alice", "password": "court"
    })
    assert response.status_code == 422
    assert "court" not in response.text
    token = register_and_login(client, "alice")
    assert client.post("/api/auth/register", json={
        "username": "ALICE", "password": "mot-de-passe-test"
    }).status_code == 409
    for username, password in [("alice", "incorrect"), ("absent", "incorrect")]:
        assert client.post("/api/auth/login", json={
            "username": username, "password": password
        }).status_code == 401
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.username == "alice"))
        stored_session = session.scalar(select(LoginSession).where(LoginSession.user_id == user.id))
        assert user.password_hash.startswith("$argon2")
        assert "mot-de-passe-test" not in user.password_hash
        assert stored_session.token_hash != token
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/auth/me").json()["username"] == "alice"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_is_rejected(api) -> None:
    client, _, engine = api
    token = register_and_login(client, "alice")
    with Session(engine) as session:
        stored_session = session.get(LoginSession, hash_token(token))
        stored_session.expires_at = int(time.time()) - 1
        session.commit()
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/courses").status_code == 401


def test_users_cannot_access_other_users_courses_or_documents(api) -> None:
    """Vérifie chaque accès aux données d'un autre compte, y compris les segments."""
    client, _, _ = api
    course_id = client.post("/api/courses", json={"title": "Privé"}).json()["id"]
    response = client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.pdf", pdf_bytes(), "application/pdf")},
    )
    document_id = response.json()["id"]
    token = register_and_login(client, "alice")
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/courses").json() == []
    assert client.get(f"/api/courses/{course_id}").status_code == 404
    assert client.patch(f"/api/courses/{course_id}", json={"title": "Autre"}).status_code == 404
    assert client.delete(f"/api/courses/{course_id}").status_code == 404
    assert client.get(f"/api/courses/{course_id}/documents").status_code == 404
    assert client.post(
        f"/api/courses/{course_id}/documents",
        files={"file": ("notes.pdf", pdf_bytes(), "application/pdf")},
    ).status_code == 404
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert client.get(f"/api/documents/{document_id}/segments").status_code == 404
    assert client.delete(f"/api/documents/{document_id}").status_code == 404
