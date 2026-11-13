import hashlib
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.models.user import LoginSession, User

password_hasher = PasswordHash.recommended()
# Effectuer une vérification même pour un nom absent limite les différences de délai.
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)
SESSION_SECONDS = 12 * 60 * 60


def hash_token(token: str) -> str:
    """Calcule l'empreinte d'un jeton aléatoire avant stockage ou recherche."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(session: Session, user: User) -> str:
    """Crée un jeton opaque, révocable et valable pendant une durée limitée."""
    token = secrets.token_urlsafe(32)
    session.add(LoginSession(
        token_hash=hash_token(token),
        user_id=user.id,
        expires_at=int(time.time()) + SESSION_SECONDS,
    ))
    session.commit()
    return token


def require_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> LoginSession:
    """Vérifie l'existence et l'expiration du jeton transmis dans Authorization."""
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Connexion requise ou session expirée.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or len(credentials.credentials) > 256:
        raise error
    login_session = session.get(LoginSession, hash_token(credentials.credentials))
    if login_session is None or login_session.expires_at <= int(time.time()):
        raise error
    return login_session


def get_current_user(
    login_session: Annotated[LoginSession, Depends(require_session)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Retourne le compte lié à la session validée."""
    user = session.get(User, login_session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Compte associé à la session introuvable.")
    return user
