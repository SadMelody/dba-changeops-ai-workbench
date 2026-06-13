"""add work order writeback logs

Revision ID: 0005_work_order_writeback_logs
Revises: 0004_run_signoff_metadata
Create Date: 2026-06-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_work_order_writeback_logs"
down_revision = "0004_run_signoff_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_order_writeback_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("source_external_id", sa.String(length=120), nullable=False),
        sa.Column("target_status", sa.String(length=64), nullable=False),
        sa.Column("webhook_url", sa.String(length=500), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_work_order_writeback_logs_id"),
        "work_order_writeback_logs",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_order_writeback_logs_run_id"),
        "work_order_writeback_logs",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_work_order_writeback_logs_run_id"), table_name="work_order_writeback_logs")
    op.drop_index(op.f("ix_work_order_writeback_logs_id"), table_name="work_order_writeback_logs")
    op.drop_table("work_order_writeback_logs")
