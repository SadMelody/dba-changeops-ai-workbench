"""add run signoff metadata

Revision ID: 0004_run_signoff_metadata
Revises: 0003_case_delivery_metadata
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_run_signoff_metadata"
down_revision = "0003_case_delivery_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column("signoff_status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("signed_by", sa.String(length=80), nullable=False, server_default=""),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("signoff_note", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("analysis_runs", sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_runs", "signed_at")
    op.drop_column("analysis_runs", "signoff_note")
    op.drop_column("analysis_runs", "signed_by")
    op.drop_column("analysis_runs", "signoff_status")
