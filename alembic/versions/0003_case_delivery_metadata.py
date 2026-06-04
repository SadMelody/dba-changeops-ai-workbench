"""add case delivery metadata

Revision ID: 0003_case_delivery_metadata
Revises: 0002_artifact_revisions
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_case_delivery_metadata"
down_revision = "0002_artifact_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("environment", sa.String(length=40), nullable=False, server_default=""))
    op.add_column("cases", sa.Column("owner", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("cases", sa.Column("approver", sa.String(length=80), nullable=False, server_default=""))
    op.add_column(
        "cases",
        sa.Column("planned_window", sa.String(length=120), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("cases", "planned_window")
    op.drop_column("cases", "approver")
    op.drop_column("cases", "owner")
    op.drop_column("cases", "environment")
