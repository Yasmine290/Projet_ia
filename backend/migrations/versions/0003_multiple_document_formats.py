"""Généralise les métadonnées de documents à PDF, Office et texte."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table reconstruit proprement la table SQLite pour rendre
    # l'ancien nombre de pages nullable et le renommer en nombre d'unités.
    with op.batch_alter_table("documents") as batch:
        batch.alter_column(
            "page_count",
            new_column_name="unit_count",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch.add_column(
            sa.Column("file_format", sa.String(length=10), nullable=False, server_default="pdf")
        )
        batch.add_column(
            sa.Column("unit_type", sa.String(length=20), nullable=False, server_default="page")
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("unit_type")
        batch.drop_column("file_format")
        batch.alter_column(
            "unit_count",
            new_column_name="page_count",
            existing_type=sa.Integer(),
            nullable=False,
        )
