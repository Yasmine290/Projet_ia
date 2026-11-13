"""Ajoute les comptes et conserve sans attribution les anciens cours."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
    )
    op.create_table(
        "login_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    # SQLite accepte une clé étrangère nullable ajoutée sans reconstruire la table
    # courses, ce qui préserve les documents qui la référencent déjà.
    op.execute(
        "ALTER TABLE courses ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE RESTRICT"
    )
    op.create_index("ix_courses_owner_id", "courses", ["owner_id"])


def downgrade() -> None:
    raise NotImplementedError("La suppression des comptes et des propriétaires n'est pas automatique.")
