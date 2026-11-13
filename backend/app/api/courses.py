from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.models.course import Course
from app.models.document import Document
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate

router = APIRouter(prefix="/api/courses", tags=["courses"])
SessionDep = Annotated[Session, Depends(get_session)]


def find_course(session: Session, course_id: int) -> Course:
    """Recherche un cours ou renvoie une erreur HTTP si son identifiant est inconnu."""
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")
    return course


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(data: CourseCreate, session: SessionDep) -> Course:
    """Enregistre le cours validé et retourne ses données persistées."""
    course = Course(title=data.title, description=data.description)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@router.get("", response_model=list[CourseRead])
def list_courses(session: SessionDep) -> list[Course]:
    """Retourne les cours dans leur ordre de création."""
    return list(session.scalars(select(Course).order_by(Course.id)).all())


@router.get("/{course_id}", response_model=CourseRead)
def read_course(course_id: int, session: SessionDep) -> Course:
    """Retourne les détails d'un cours existant."""
    return find_course(session, course_id)


@router.patch("/{course_id}", response_model=CourseRead)
def update_course(course_id: int, data: CourseUpdate, session: SessionDep) -> Course:
    """Modifie uniquement les champs transmis, sans accepter de valeur nulle."""
    course = find_course(session, course_id)
    changes = data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Les champs ne peuvent pas être nuls.")
    for field, value in changes.items():
        setattr(course, field, value)
    session.commit()
    session.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, session: SessionDep) -> Response:
    """Supprime un cours uniquement après la suppression de ses documents."""
    course = find_course(session, course_id)
    # Empêche de laisser des fichiers orphelins : supprimer les documents d'abord.
    if session.scalar(select(Document.id).where(Document.course_id == course_id).limit(1)):
        raise HTTPException(
            status_code=409, detail="Supprimez les documents du cours avant le cours."
        )
    session.delete(course)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
