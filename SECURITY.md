# Security Policy

This project is an interview-ready DBA ChangeOps demo. It is designed for
controlled demonstration and trial deployment, not direct production DB2
execution.

## Supported Scope

Security expectations apply to the current repository and first-release product
boundary:

- FastAPI application routes and JSON APIs.
- SQLAlchemy/Alembic persistence.
- OpenAI-compatible LLM adapter and offline fallback.
- Work-order import, Webhook writeback, writeback logs, and retry behavior.
- Markdown/PDF exports and release packages.
- Render, Railway, Fly.io, Docker, and CI delivery paths.

Out of scope unless explicitly implemented later:

- Direct production DB2 connectivity or SQL execution.
- Enterprise IAM, multi-tenant authorization, or organization hierarchy.
- Vendor-specific ITSM state machines and approval workflows.

## Secrets And Configuration

Do not commit real secrets or private endpoints. Keep these values in local
environment variables or hosting-provider secret stores:

- `DATABASE_URL`
- `LLM_API_KEY`
- `ITSM_WEBHOOK_URL`
- `ITSM_WEBHOOK_TOKEN`

`.env`, local SQLite databases, logs, pid files, Python caches, and release
working directories are excluded from git and release packages.

## Audit Redaction

The application keeps audit evidence while reducing secret exposure:

- LLM request and response payloads are sanitized before persistence.
- LLM provider failure messages are sanitized before they are stored in analysis
  runs or call logs.
- Common passwords, API keys, access keys, signatures, tokens, and database
  connection string passwords are redacted in audit payloads.
- Sensitive-looking dictionary key names, such as `token=...` or
  `signature=...`, are sanitized before audit payloads are stored or returned.
- Authorization, Basic Auth, Cookie, credential, and session-style audit fields
  are redacted before persistence.
- Webhook dispatch uses the configured raw `ITSM_WEBHOOK_URL`, but persisted
  logs and API responses store a redacted URL.
- Webhook URL query keys containing token/key/secret/signature/password markers
  are redacted.
- Basic Auth passwords in Webhook URLs are redacted.
- External work-order URLs are normalized through the same URL redaction rules
  before they are stored in case context or returned in writeback payloads.
- External work-order labels and metadata are sanitized before they are stored
  in case context, sent to the LLM adapter, or returned in writeback payloads.
- External Webhook response bodies are sanitized before they are stored in
  writeback logs or returned through JSON APIs.
- Webhook network failure messages are sanitized before they are stored in
  writeback logs or returned through JSON APIs.

These rules are regression-tested in `tests/test_workflow.py`.

## Release Checks

Before sharing or deploying the project, run:

```powershell
.\.venv\Scripts\python.exe -m pytest
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean_release_artifacts.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\release_readiness.ps1 -SkipRuntime
```

For a running local app, use:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\final_acceptance.ps1 -BaseUrl http://127.0.0.1:8000 -PythonCommand .\.venv\Scripts\python.exe
```

For online release verification, use `scripts/verify_online_release.ps1` and
`scripts/delivery_status.ps1` with the verified `DemoUrl`. Do not claim strict
public delivery is complete until a public `VideoUrl` is also verified.

## Reporting Issues

For this portfolio project, report security issues privately to the repository
owner before opening a public issue. Include:

- affected route, script, or document
- minimal reproduction steps
- whether a real secret or private endpoint was exposed
- suggested remediation if known

Do not include real API keys, database credentials, private Webhook URLs, or
production data in reports.
