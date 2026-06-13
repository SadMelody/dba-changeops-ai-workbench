from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import create_db, get_db
from app.demo_data import seed_demo_data
from app.exporter import export_markdown, export_pdf_bytes
from app.models import Artifact, Case
from app.services import (
    analyze_case,
    artifact_content_diff,
    approve_artifact,
    approve_run_artifacts,
    create_case,
    delivery_summary,
    event_label,
    format_dt,
    get_artifact_with_revisions,
    get_case,
    get_run,
    list_cases,
    normalize_artifact_content,
    operational_status,
    provider_label,
    run_signoff_summary,
    signoff_run,
    status_label,
    update_artifact_content,
    workbench_summary,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    db = next(get_db())
    try:
        seed_demo_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="DBA ChangeOps AI 工作台", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["dt"] = format_dt
templates.env.filters["status_label"] = status_label
templates.env.filters["provider_label"] = provider_label
templates.env.filters["event_label"] = event_label
templates.env.globals["delivery_summary"] = delivery_summary
templates.env.globals["workbench_summary"] = workbench_summary
templates.env.globals["artifact_content_diff"] = artifact_content_diff
templates.env.globals["run_signoff_summary"] = run_signoff_summary


def _recommended_demo_case(cases: list[Case]) -> Case | None:
    for case in cases:
        if case.title == "DB2 客户订单慢查询索引变更":
            return case
    return cases[0] if cases else None


async def _json_object(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="请求体必须是合法 JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="请求体必须是 JSON 对象")
    return data


def _validation_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = 409 if "全部确认" in detail else 422
    return HTTPException(status_code=status_code, detail=detail)


@app.get("/healthz")
def healthz(db: Session = Depends(get_db)) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(
            {
                "status": "error",
                "database": "error",
                "detail": str(exc),
            },
            status_code=503,
        )
    return JSONResponse(
        {
            "status": "ok",
            "database": "ok",
            "service": "dba-changeops-ai-workbench",
        }
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cases = list_cases(db)
    selected = cases[0] if cases else None
    latest_run = selected.runs[0] if selected and selected.runs else None
    summary = workbench_summary(cases)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "active_nav": "cases",
            "cases": cases,
            "selected": selected,
            "latest_run": latest_run,
            "workbench": summary,
        },
    )


@app.get("/demo", response_class=HTMLResponse)
def demo_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cases = list_cases(db)
    demo_case = _recommended_demo_case(cases)
    latest_run = demo_case.runs[0] if demo_case and demo_case.runs else None
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "active_nav": "demo",
            "cases": cases,
            "demo_case": demo_case,
            "latest_run": latest_run,
            "workbench": workbench_summary(cases),
        },
    )


@app.get("/ops", response_class=HTMLResponse)
def operations_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    cases = list_cases(db)
    status = operational_status(cases, get_settings(), database_ok=True)
    return templates.TemplateResponse(
        request,
        "operations.html",
        {
            "active_nav": "ops",
            "status": status,
            "workbench": status["summary"],
        },
    )


@app.get("/api/system/status")
def system_status_api(db: Session = Depends(get_db)) -> JSONResponse:
    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    cases = list_cases(db) if database_ok else []
    status = operational_status(cases, get_settings(), database_ok=database_ok)
    return JSONResponse(status, status_code=200 if database_ok else 503)


@app.post("/demo/start")
def start_demo(db: Session = Depends(get_db)) -> RedirectResponse:
    cases = list_cases(db)
    demo_case = _recommended_demo_case(cases)
    if not demo_case:
        raise HTTPException(status_code=404, detail="暂无可试跑案例")
    run = analyze_case(db, demo_case)
    return RedirectResponse(f"/cases/{demo_case.id}/runs/{run.id}", status_code=303)


@app.post("/demo/complete")
def complete_demo(db: Session = Depends(get_db)) -> RedirectResponse:
    cases = list_cases(db)
    demo_case = _recommended_demo_case(cases)
    if not demo_case:
        raise HTTPException(status_code=404, detail="暂无可试跑案例")
    run = analyze_case(db, demo_case)
    approved_run = approve_run_artifacts(db, run.id)
    if not approved_run:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    signoff_run(
        db,
        approved_run.id,
        signed_by=demo_case.approver or demo_case.owner or "变更审批人",
        note="演示交付包已完成复核，允许用于变更评审讲解。",
    )
    return RedirectResponse(f"/cases/{demo_case.id}/runs/{run.id}", status_code=303)


@app.get("/cases/new", response_class=HTMLResponse)
def new_case_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "new_case.html", {"active_nav": "cases"})


@app.post("/cases")
def create_case_form(
    title: str = Form(...),
    db_type: str = Form("DB2 LUW"),
    target_system: str = Form(""),
    change_type: str = Form("Database change"),
    priority: str = Form("P2"),
    environment: str = Form(""),
    owner: str = Form(""),
    approver: str = Form(""),
    planned_window: str = Form(""),
    business_context: str = Form(""),
    source_sql: str = Form(""),
    schema_notes: str = Form(""),
    constraints: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        case = create_case(
            db,
            {
                "title": title,
                "db_type": db_type,
                "target_system": target_system,
                "change_type": change_type,
                "priority": priority,
                "environment": environment,
                "owner": owner,
                "approver": approver,
                "planned_window": planned_window,
                "business_context": business_context,
                "source_sql": source_sql,
                "schema_notes": schema_notes,
                "constraints": constraints,
            },
        )
    except ValueError as exc:
        raise _validation_error(exc) from exc
    return RedirectResponse(f"/cases/{case.id}", status_code=303)


@app.post("/api/cases")
async def create_case_api(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    data = await _json_object(request)
    try:
        case = create_case(db, data)
    except ValueError as exc:
        raise _validation_error(exc) from exc
    return JSONResponse({"id": case.id, "title": case.title, "status": case.status})


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail(case_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return templates.TemplateResponse(
        request,
        "case_detail.html",
        {"active_nav": "cases", "case": case},
    )


@app.post("/cases/{case_id}/analyze")
def analyze_case_form(case_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    run = analyze_case(db, case)
    return RedirectResponse(f"/cases/{case.id}/runs/{run.id}", status_code=303)


@app.post("/api/cases/{case_id}/analyze")
def analyze_case_api(case_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    run = analyze_case(db, case)
    return JSONResponse(
        {
            "run_id": run.id,
            "case_id": case.id,
            "status": run.status,
            "provider": run.provider,
            "model": run.model,
            "artifact_count": len(run.artifacts),
            "delivery": delivery_summary(run),
            "signoff": run_signoff_summary(run),
            "run_url": f"/cases/{case.id}/runs/{run.id}",
            "message": "交付方案已生成",
        }
    )


@app.post("/api/cases/{case_id}/retry")
def retry_case_analysis_api(case_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    run = analyze_case(db, case)
    return JSONResponse(
        {
            "run_id": run.id,
            "case_id": case.id,
            "status": run.status,
            "provider": run.provider,
            "model": run.model,
            "artifact_count": len(run.artifacts),
            "delivery": delivery_summary(run),
            "signoff": run_signoff_summary(run),
            "run_url": f"/cases/{case.id}/runs/{run.id}",
            "message": "已重新生成交付方案",
        }
    )


@app.get("/api/cases/{case_id}/runs")
def runs_api(case_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return JSONResponse(
        {
            "case_id": case.id,
            "runs": [
                {
                    "id": run.id,
                    "status": run.status,
                    "provider": run.provider,
                    "model": run.model,
                    "completed_at": format_dt(run.completed_at),
                    "summary": run.summary,
                    "delivery": delivery_summary(run),
                    "signoff": run_signoff_summary(run),
                }
                for run in case.runs
            ],
        }
    )


@app.get("/api/artifacts/{artifact_id}/revisions")
def artifact_revisions_api(artifact_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    artifact = get_artifact_with_revisions(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="交付物不存在")
    revisions = sorted(artifact.revisions, key=lambda revision: revision.version, reverse=True)
    return JSONResponse(
        {
            "artifact_id": artifact.id,
            "title": artifact.title,
            "revisions": [
                {
                    "id": revision.id,
                    "version": revision.version,
                    "event": revision.event,
                    "event_label": event_label(revision.event),
                    "status": revision.status,
                    "status_label": status_label(revision.status),
                    "created_at": format_dt(revision.created_at),
                    "content": revision.content,
                }
                for revision in revisions
            ],
        }
    )


@app.get("/api/artifacts/{artifact_id}/diff")
def artifact_diff_api(artifact_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    artifact = get_artifact_with_revisions(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="交付物不存在")
    return JSONResponse(
        {
            "artifact_id": artifact.id,
            "title": artifact.title,
            "diff": artifact_content_diff(artifact),
        }
    )


@app.get("/cases/{case_id}/runs/{run_id}", response_class=HTMLResponse)
def run_detail(
    case_id: int, run_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    case = get_case(db, case_id)
    run = get_run(db, run_id)
    if not case or not run or run.case_id != case.id:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {"active_nav": "demo", "case": case, "run": run},
    )


@app.post("/api/runs/{run_id}/approve-all")
def approve_run_artifacts_api(run_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    run = approve_run_artifacts(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return JSONResponse(
        {
            "run_id": run.id,
            "case_id": run.case_id,
            "delivery": delivery_summary(run),
            "signoff": run_signoff_summary(run),
            "message": "交付包已确认",
        }
    )


@app.post("/api/runs/{run_id}/signoff")
async def signoff_run_api(run_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    data = await _json_object(request)
    try:
        run = signoff_run(
            db,
            run_id,
            signed_by=str(data.get("signed_by") or ""),
            note=str(data.get("note") or data.get("signoff_note") or ""),
        )
    except ValueError as exc:
        raise _validation_error(exc) from exc
    if not run:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return JSONResponse(
        {
            "run_id": run.id,
            "case_id": run.case_id,
            "delivery": delivery_summary(run),
            "signoff": run_signoff_summary(run),
            "message": "交付包已签收",
        }
    )


@app.post("/api/artifacts/{artifact_id}/approve")
def approve_artifact_api(artifact_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    artifact = approve_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="交付物不存在")
    return JSONResponse(
        {
            "id": artifact.id,
            "status": artifact.status,
            "approved_at": format_dt(artifact.approved_at),
        }
    )


@app.post("/api/artifacts/{artifact_id}")
async def update_artifact_api(
    artifact_id: int, request: Request, db: Session = Depends(get_db)
) -> JSONResponse:
    data = await _json_object(request)
    try:
        content = normalize_artifact_content(str(data.get("content") or ""))
    except ValueError as exc:
        raise _validation_error(exc) from exc
    artifact = update_artifact_content(db, artifact_id, content)
    if not artifact:
        raise HTTPException(status_code=404, detail="交付物不存在")
    return JSONResponse(
        {
            "id": artifact.id,
            "status": artifact.status,
            "updated_at": format_dt(artifact.updated_at),
        }
    )


@app.post("/runs/{run_id}/approve-all")
def approve_run_artifacts_form(run_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    run = approve_run_artifacts(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return RedirectResponse(f"/cases/{run.case_id}/runs/{run.id}", status_code=303)


@app.post("/runs/{run_id}/signoff")
def signoff_run_form(
    run_id: int,
    signed_by: str = Form(""),
    signoff_note: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        run = signoff_run(db, run_id, signed_by=signed_by, note=signoff_note)
    except ValueError as exc:
        raise _validation_error(exc) from exc
    if not run:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return RedirectResponse(f"/cases/{run.case_id}/runs/{run.id}", status_code=303)


@app.post("/artifacts/{artifact_id}/approve")
def approve_artifact_form(artifact_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    artifact = approve_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="交付物不存在")
    return RedirectResponse(f"/cases/{artifact.case_id}/runs/{artifact.run_id}", status_code=303)


@app.post("/artifacts/{artifact_id}")
def update_artifact_form(
    artifact_id: int, content: str = Form(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    try:
        content = normalize_artifact_content(content)
        artifact = update_artifact_content(db, artifact_id, content)
    except ValueError as exc:
        raise _validation_error(exc) from exc
    if not artifact:
        raise HTTPException(status_code=404, detail="交付物不存在")
    return RedirectResponse(f"/cases/{artifact.case_id}/runs/{artifact.run_id}", status_code=303)


@app.get("/cases/{case_id}/export")
def export_case_markdown(case_id: int, db: Session = Depends(get_db)) -> Response:
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    filename = f"changeops-case-{case.id}.md"
    return Response(
        export_markdown(case),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/cases/{case_id}/export.pdf")
def export_case_pdf(case_id: int, db: Session = Depends(get_db)) -> Response:
    case = get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    filename = f"changeops-case-{case.id}.pdf"
    return Response(
        export_pdf_bytes(case),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
