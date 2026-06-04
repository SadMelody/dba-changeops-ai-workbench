from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    db_type: Mapped[str] = mapped_column(String(40), default="DB2")
    target_system: Mapped[str] = mapped_column(String(120), default="Core banking")
    change_type: Mapped[str] = mapped_column(String(80), default="DDL change")
    priority: Mapped[str] = mapped_column(String(24), default="P2")
    environment: Mapped[str] = mapped_column(String(40), default="")
    owner: Mapped[str] = mapped_column(String(80), default="")
    approver: Mapped[str] = mapped_column(String(80), default="")
    planned_window: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    business_context: Mapped[str] = mapped_column(Text, default="")
    source_sql: Mapped[str] = mapped_column(Text, default="")
    schema_notes: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="AnalysisRun.id.desc()"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    provider: Mapped[str] = mapped_column(String(80), default="fixture")
    model: Mapped[str] = mapped_column(String(120), default="fixture")
    prompt_version: Mapped[str] = mapped_column(String(32), default="changeops-v1")
    summary: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    signoff_status: Mapped[str] = mapped_column(String(32), default="pending")
    signed_by: Mapped[str] = mapped_column(String(80), default="")
    signoff_note: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped[Case] = relationship(back_populates="runs")
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Artifact.id"
    )
    llm_logs: Mapped[list["LLMCallLog"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="LLMCallLog.id.desc()"
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    case: Mapped[Case] = relationship(back_populates="artifacts")
    run: Mapped[AnalysisRun] = relationship(back_populates="artifacts")
    revisions: Mapped[list["ArtifactRevision"]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="ArtifactRevision.version.desc()",
    )


class ArtifactRevision(Base):
    __tablename__ = "artifact_revisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    version: Mapped[int] = mapped_column(default=1)
    event: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    artifact: Mapped[Artifact] = relationship(back_populates="revisions")
    run: Mapped[AnalysisRun] = relationship()


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32))
    latency_ms: Mapped[int] = mapped_column(default=0)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped[AnalysisRun] = relationship(back_populates="llm_logs")


class DemoFixture(Base):
    __tablename__ = "demo_fixtures"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
