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

## Agent Operating Contract

Use this file as the project boundary before making changes in this repository:

- Start each work session by checking the current git state and reading the
  task-relevant code/docs before editing.
- If a request is ambiguous, choose the path that strengthens the DBA ChangeOps
  demo product instead of widening the product surface.
- Keep implementation, documentation, demo artifacts, and release scripts aligned;
  do not leave the project in a state where the demo says one thing and the code
  does another.
- Prefer completing one demonstrable workflow end to end over adding partial
  capabilities in several directions.
- Preserve the interview/demo narrative: an evaluator should be able to understand
  what the product does, run it, verify it, and see evidence without private
  infrastructure.
- Treat unverified public claims as defects. A URL, video, integration, or model
  path is only "ready" after the relevant check has passed.
- If existing local changes are present, assume they are user or prior-agent work;
  inspect them, build on them when relevant, and do not revert them without an
  explicit instruction.
- When resuming a paused goal, do not restart a broad project audit by default.
  Use the minimum current-state check needed to continue safely, usually
  `git status --short --branch` plus the diff for files you are about to touch.
- If the same external push/network failure has already been observed, attempt at
  most one push per continuation unless the user explicitly asks for more
  retries.

## Default Decision Rules

When a future task is underspecified, choose the option that makes the existing
interview/demo path more credible before adding new surface area:

1. Prefer fixing evidence, reproducibility, and release honesty over visual polish.
2. Prefer tightening the existing DBA change workflow over adding unrelated AI
   features.
3. Prefer one complete, testable scenario over several partial scenarios.
4. Prefer local/demo compatibility over cloud-only behavior.
5. Prefer explicit pending status over placeholder links, fake integrations, or
   unverifiable claims.

If a request conflicts with these rules, follow the user's direct instruction,
but call out the tradeoff in the final report.

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

## Workflow Boundary

Protect the core product loop before adding anything else:

1. Import or describe a DBA change request.
2. Generate reviewable delivery materials through the LLM adapter or offline
   DB2 fixture fallback.
3. Review, edit, diff, approve, and sign off on the generated materials.
4. Export evidence and optionally write back a sanitized status payload to a
   generic external work-order endpoint.
5. Keep audit records useful for demo review without exposing credentials,
   private URLs, raw provider secrets, or sensitive external response bodies.

Changes that do not support this loop should be deferred unless the user
explicitly asks for them.

## Current Improvement Priorities

When continuing project completion, prioritize work in this order unless the user
explicitly changes direction:

1. Keep the deployed demo verifiable and reproducible.
2. Protect audit/security boundaries, especially secrets in LLM and Webhook paths.
3. Improve the DBA workflow depth where it helps the interview story.
4. Keep release evidence current: docs, sample exports, screenshots, checks, and
   public delivery status.
5. Defer polish that does not improve evaluator understanding or delivery
   confidence.

## Release Status Semantics

Use precise status language throughout scripts, docs, and final reports:

- `demo_ready`: the core product demo is runnable and verifiable for interview
  purposes.
- `strict_public_ready`: all public delivery inputs are verified, including both
  `DemoUrl` and `VideoUrl`.
- `demo-only`: the deployed app can be evaluated, but one or more public delivery
  assets are intentionally pending.
- `pending`: an external item has not been produced or verified yet.

Do not treat a skipped video as a code defect. The project may be demo-ready
while strict public delivery remains incomplete because `VideoUrl` is pending.

## External Inputs And Delivery Boundary

Treat external delivery inputs as project metadata, not hard-coded application
behavior:

- `DemoUrl`: the verified online demo URL for the deployed web service.
- `VideoUrl`: the verified demo walkthrough video URL, only when video recording
  is actually completed.
- `LLM_*`: OpenAI-compatible model configuration used at runtime; the app must
  keep working through the offline fixture path when these values are absent.
- `ITSM_WEBHOOK_URL`: the raw Webhook target used only for dispatch; logs,
  persisted audit payloads, API responses, docs, and tests must not expose
  secrets from this URL or from external response bodies.

Do not claim a public URL, video, model integration, or ITSM writeback is ready
unless it has been verified in the current working state. If an item is not yet
verified, document it as pending instead of filling in a placeholder as fact.

## Completion Definition

For this project, "done" means the feature is useful in the interview/demo path
and has evidence:

- routes, services, persistence, and UI remain aligned
- regression tests or a focused script cover the behavior
- release/deployment docs match the shipped behavior
- generated demo artifacts are refreshed when public evidence changes
- secrets and private URLs are never committed or shown in durable logs

Video production is intentionally outside the active implementation path unless
the user explicitly re-enables it.

For project-completion work, do not mark the overall goal complete while any
required external delivery input is still pending. Instead, report the verified
state and the exact remaining input.

## Evidence And Demo Discipline

- Prefer reproducible local evidence over screenshots or claims that cannot be
  regenerated from the repository.
- Keep demo artifacts, release scripts, and documentation synchronized when
  public status changes.
- If a public demo URL is available, verify it before recording it as `DemoUrl`.
- If walkthrough video production is skipped, keep `VideoUrl` explicitly
  `pending` and do not downgrade the runnable demo for that reason alone.
- If a check is skipped, final reports and docs must say what was not verified.

## Engineering Rules

- Keep changes small, reviewable, and aligned with existing patterns.
- Prefer service-layer functions over putting business logic directly in routes.
- Add or update Alembic migrations whenever persistent models change.
- Keep `create_db()` compatible with local/demo startup; the app should still
  self-initialize for interviews.
- Do not add dependencies without a clear need and a project-standard precedent.
- Do not remove offline fallback behavior; demos must work without `LLM_API_KEY`.
- Do not commit secrets, real API keys, real DB credentials, or private ITSM URLs.
- Sanitize user-provided prompts, Webhook URLs, authorization values, and external
  response bodies before storing them in audit records or returning them through
  public JSON endpoints.
- Preserve Chinese user-facing copy unless deliberately updating product wording.
- If a feature affects public behavior, update `README.md` and relevant files in
  `docs/` in the same change.
- When touching release scripts or generated artifacts, keep the script output,
  README status block, and `docs/` evidence pages in sync.
- Avoid creating parallel documentation sources for the same fact; link or update
  the existing source of truth instead.

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
