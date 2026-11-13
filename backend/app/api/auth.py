from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.models.user import LoginSession, User
from app.schemas.auth import AccountCreate, LoginRequest, TokenRead, UserRead
from app.services.auth import (
    SESSION_SECONDS, create_session, dummy_hash, get_current_user, password_hasher,
    require_session,
)

router = APIRouter(prefix="/api/auth", tags=["authentification"])
SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: AccountCreate, session: SessionDep) -> User:
    """Crée un compte local avec un mot de passe haché par Argon2."""
    user = User(username=data.username, password_hash=password_hasher.hash(data.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur est déjà utilisé.") from exc
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenRead)
def login(data: LoginRequest, response: Response, session: SessionDep) -> TokenRead:
    """Vérifie les identifiants puis retourne un jeton de session révocable."""
    user = session.scalar(select(User).where(User.username == data.username))
    valid = password_hasher.verify(data.password, user.password_hash if user else dummy_hash)
    if user is None or not valid:
        raise HTTPException(status_code=401, detail="Identifiants invalides.")
    response.headers["Cache-Control"] = "no-store"
    return TokenRead(access_token=create_session(session, user), expires_in=SESSION_SECONDS)


@router.get("/me", response_model=UserRead)
def current_user(user: UserDep) -> User:
    """Retourne le profil du compte connecté."""
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    login_session: Annotated[LoginSession, Depends(require_session)],
    session: SessionDep,
) -> Response:
    """Révoque immédiatement la session utilisée pour cet appel."""
    session.delete(login_session)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
