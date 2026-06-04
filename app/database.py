from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(database_url: str) -> dict:
    if database_url == "sqlite:///:memory:":
        return {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


settings = get_settings()
engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db() -> None:
    from app import models  # noqa: F401

    url = make_url(settings.database_url)
    if url.drivername == "sqlite" and url.database not in {None, "", ":memory:"}:
        from pathlib import Path

        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_case_delivery_columns()
    _ensure_analysis_run_signoff_columns()


def _ensure_case_delivery_columns() -> None:
    inspector = inspect(engine)
    if "cases" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("cases")}
    required = {
        "environment": "VARCHAR(40)",
        "owner": "VARCHAR(80)",
        "approver": "VARCHAR(80)",
        "planned_window": "VARCHAR(120)",
    }
    missing = [name for name in required if name not in existing]
    if not missing:
        return
    with engine.begin() as connection:
        for name in missing:
            connection.execute(
                text(f"ALTER TABLE cases ADD COLUMN {name} {required[name]} NOT NULL DEFAULT ''")
            )


def _ensure_analysis_run_signoff_columns() -> None:
    inspector = inspect(engine)
    if "analysis_runs" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("analysis_runs")}
    required = {
        "signoff_status": "VARCHAR(32) NOT NULL DEFAULT 'pending'",
        "signed_by": "VARCHAR(80) NOT NULL DEFAULT ''",
        "signoff_note": "TEXT NOT NULL DEFAULT ''",
        "signed_at": "DATETIME",
    }
    missing = [name for name in required if name not in existing]
    if not missing:
        return
    with engine.begin() as connection:
        for name in missing:
            connection.execute(text(f"ALTER TABLE analysis_runs ADD COLUMN {name} {required[name]}"))
