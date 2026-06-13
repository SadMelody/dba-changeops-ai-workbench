# Project Agent Instructions

This file applies to the entire `dba-changeops-ai-workbench` repository.

## Project Purpose

DBA ChangeOps AI 工作台 is a portfolio-ready AI delivery workbench for database
operations and DBA change planning. The product turns a database change request,
SQL, schema notes, or incident description into structured, reviewable delivery
materials:

- risk assessment
- execution runbook
- rollback plan
- pre-check SQL
- acceptance checklist
- communication summary
- audit logs, signoff records, exports, and work-order writeback evidence

Treat this as a productized workflow tool, not a generic chatbot demo.

## Current Product Boundary

Keep the first-release scope focused on a stable interview/demo product:

- DB2/database operations change scenarios.
- FastAPI backend with Jinja2 server-rendered pages and local CSS/JS.
- SQLAlchemy models with Alembic migrations.
- SQLite for local/demo use and PostgreSQL-compatible `DATABASE_URL` for deploys.
- OpenAI-compatible chat-completions adapter with offline DB2 fixture fallback.
- Manual review workflow: edit, version, diff, approve, approve all, sign off.
- Markdown/PDF delivery exports.
- External work-order import, standard writeback payload, configurable ITSM
  Webhook send, writeback logs, and failed writeback retry.
- Deployment readiness for Render, Railway, Fly.io, Docker, and CI.

Do not expand the project into these areas unless the user explicitly asks:

- direct production DB2 connectivity or execution against a real database
- enterprise IAM, multi-tenant authorization, or organization hierarchy
- full ITSM vendor-specific field mapping/state machines
- multi-level approval engines
- a SPA/frontend build pipeline
- a broad model-evaluation platform

When extending work-order integration, keep the generic boundary clear:
standard payloads and generic Webhook transport are in scope; vendor-specific
Jira/ServiceNow/enterprise approval semantics are a later adapter layer.

## Engineering Rules

- Keep changes small, reviewable, and aligned with existing patterns.
- Prefer service-layer functions over putting business logic directly in routes.
- Add or update Alembic migrations whenever persistent models change.
- Keep `create_db()` compatible with local/demo startup; the app should still
  self-initialize for interviews.
- Do not add dependencies without a clear need and a project-standard precedent.
- Do not remove offline fallback behavior; demos must work without `LLM_API_KEY`.
- Do not commit secrets, real API keys, real DB credentials, or private ITSM URLs.
- Preserve Chinese user-facing copy unless deliberately updating product wording.
- If a feature affects public behavior, update `README.md` and relevant files in
  `docs/` in the same change.

## Key Files

- `app/main.py`: FastAPI routes and page handlers.
- `app/services.py`: workflow/business logic.
- `app/models.py`: SQLAlchemy ORM models.
- `app/integrations.py`: external work-order import/writeback helpers.
- `app/llm.py`: OpenAI-compatible model adapter and audit sanitization.
- `app/demo_data.py`: offline DB2 fixtures and fallback delivery content.
- `app/evaluation.py`: offline scenario evaluation.
- `app/templates/`: server-rendered UI.
- `app/static/`: local CSS and browser enhancements.
- `alembic/versions/`: schema migrations.
- `tests/test_workflow.py`: main regression suite.
- `scripts/`: smoke, release, packaging, and deployment audit scripts.
- `docs/`: API, architecture, deployment, interview, release, and handoff docs.

## Verification

Use the strongest practical check for the change:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

For DB2 fixture/fallback changes:

```powershell
.\.venv\Scripts\python.exe -B -m app.evaluation
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\evaluate_demo_fixtures.ps1 -PythonCommand .\.venv\Scripts\python.exe
```

For release/deployment material changes:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_config_audit.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\release_readiness.ps1 -SkipRuntime
```

For end-to-end verification with a running app:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\final_acceptance.ps1 -BaseUrl http://127.0.0.1:8000 -PythonCommand .\.venv\Scripts\python.exe
```

If full runtime verification is not practical, state the gap explicitly in the
final report.

## Documentation Discipline

Keep these documents consistent with shipped behavior:

- `README.md`: high-level capability and demo path.
- `docs/API.md`: endpoint contracts and examples.
- `docs/ARCHITECTURE.md`: product boundary and data model.
- `docs/COMPLETION_AUDIT.md`: capability-to-evidence map.
- `docs/INTERVIEW_QA.md`: honest interview boundary and expansion plan.
- `docs/DEPLOYMENT.md` and `docs/RELEASE_CHECKLIST.md`: environment and deploy
  instructions.
- `docs/HANDOFF_CHECKLIST.md`: final capability handoff.

Do not claim an online deployment, video, or external integration works unless it
has been verified in the current state or clearly documented as pending.
