import argparse

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.database import get_engine
from app.models.course import Course
from app.models.user import User


def main() -> None:
    """Attribue explicitement les anciens cours sans propriétaire à un compte existant."""
    parser = argparse.ArgumentParser(
        description="Attribuer tous les anciens cours sans propriétaire à un compte local."
    )
    parser.add_argument("username", help="Nom du compte local destinataire.")
    parser.add_argument(
        "--confirm", action="store_true", help="Confirme l'attribution de tous les anciens cours."
    )
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Ajoutez --confirm après avoir vérifié le compte destinataire.")
    with Session(get_engine()) as session:
        user = session.scalar(select(User).where(User.username == args.username.strip().lower()))
        if user is None:
            parser.error("Compte introuvable. Créez-le avant d'attribuer les cours.")
        result = session.execute(
            update(Course).where(Course.owner_id.is_(None)).values(owner_id=user.id)
        )
        session.commit()
        print(f"{result.rowcount} cours attribué(s) au compte {user.username}.")


if __name__ == "__main__":
    main()
