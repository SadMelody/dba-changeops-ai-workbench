"""add artifact revision history

Revision ID: 0002_artifact_revisions
Revises: 0001_initial_schema
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_artifact_revisions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_artifact_revisions_artifact_id"),
        "artifact_revisions",
        ["artifact_id"],
        unique=False,
    )
    op.create_index(op.f("ix_artifact_revisions_id"), "artifact_revisions", ["id"], unique=False)
    op.create_index(
        op.f("ix_artifact_revisions_run_id"),
        "artifact_revisions",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_artifact_revisions_run_id"), table_name="artifact_revisions")
    op.drop_index(op.f("ix_artifact_revisions_id"), table_name="artifact_revisions")
    op.drop_index(op.f("ix_artifact_revisions_artifact_id"), table_name="artifact_revisions")
    op.drop_table("artifact_revisions")
