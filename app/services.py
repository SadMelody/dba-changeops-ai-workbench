from __future__ import annotations

import difflib
from datetime import timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy.engine import make_url
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.demo_data import ARTIFACT_TITLES
from app.llm import LLMClient
from app.models import AnalysisRun, Artifact, ArtifactRevision, Case, LLMCallLog, utc_now


STATUS_LABELS = {
    "draft": "草稿",
    "running": "生成中",
    "completed": "已完成",
    "failed": "失败",
    "approved": "已确认",
    "analysis_ready": "方案已生成",
    "success": "调用成功",
    "fallback": "兜底成功",
    "pending": "等待中",
    "signed": "已签收",
}

PROVIDER_LABELS = {
    "fixture": "离线兜底",
    "offline-demo": "内置兜底",
    "openai-compatible": "OpenAI 兼容接口",
    "pending": "等待中",
}

EVENT_LABELS = {
    "generated": "AI 生成",
    "edited": "人工编辑",
    "approved": "人工确认",
}

CASE_STRING_LIMITS = {
    "title": 180,
    "db_type": 40,
    "target_system": 120,
    "change_type": 80,
    "priority": 24,
    "environment": 40,
    "owner": 80,
    "approver": 80,
    "planned_window": 120,
}

CASE_TEXT_LIMITS = {
    "business_context": 4000,
    "source_sql": 12000,
    "schema_notes": 4000,
    "constraints": 4000,
}

CASE_FIELD_LABELS = {
    "title": "标题",
    "db_type": "数据库类型",
    "target_system": "目标系统",
    "change_type": "变更类型",
    "priority": "优先级",
    "environment": "环境",
    "owner": "负责人",
    "approver": "审批人",
    "planned_window": "计划窗口",
    "business_context": "业务背景",
    "source_sql": "SQL 或操作命令",
    "schema_notes": "表结构说明",
    "constraints": "约束条件",
}

ALLOWED_PRIORITIES = {"P1", "P2", "P3", "P4"}
ARTIFACT_CONTENT_LIMIT = 20000
SIGNOFF_NAME_LIMIT = 80
SIGNOFF_NOTE_LIMIT = 2000


def _field_text(data: dict[str, Any], field: str, default: str = "") -> str:
    value = data.get(field, default)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{CASE_FIELD_LABELS.get(field, field)}必须是文本")
    return value.strip()


def normalize_case_data(data: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    errors: list[str] = []

    for field, limit in CASE_STRING_LIMITS.items():
        try:
            normalized[field] = _field_text(data, field, "DB2" if field == "db_type" else "")
        except ValueError as exc:
            errors.append(str(exc))
            normalized[field] = ""
            continue
        if len(normalized[field]) > limit:
            errors.append(f"{CASE_FIELD_LABELS[field]}不能超过 {limit} 个字符")

    for field, limit in CASE_TEXT_LIMITS.items():
        try:
            normalized[field] = _field_text(data, field)
        except ValueError as exc:
            errors.append(str(exc))
            normalized[field] = ""
            continue
        if len(normalized[field]) > limit:
            errors.append(f"{CASE_FIELD_LABELS[field]}不能超过 {limit} 个字符")

    if not normalized["title"]:
        errors.append("标题不能为空")
    normalized["db_type"] = normalized["db_type"] or "DB2"
    normalized["change_type"] = normalized["change_type"] or "数据库变更"
    normalized["priority"] = (normalized["priority"] or "P2").upper()
    if normalized["priority"] not in ALLOWED_PRIORITIES:
        errors.append("优先级只能是 P1、P2、P3 或 P4")

    if errors:
        raise ValueError("；".join(errors))
    return normalized


def normalize_artifact_content(content: str) -> str:
    normalized = content.strip()
    if not normalized:
        raise ValueError("交付物内容不能为空")
    if len(normalized) > ARTIFACT_CONTENT_LIMIT:
        raise ValueError(f"交付物内容不能超过 {ARTIFACT_CONTENT_LIMIT} 个字符")
    return normalized


def normalize_signoff_input(signed_by: str, note: str) -> tuple[str, str]:
    signed_by = signed_by.strip()
    note = note.strip()
    if len(signed_by) > SIGNOFF_NAME_LIMIT:
        raise ValueError(f"签收人不能超过 {SIGNOFF_NAME_LIMIT} 个字符")
    if len(note) > SIGNOFF_NOTE_LIMIT:
        raise ValueError(f"签收说明不能超过 {SIGNOFF_NOTE_LIMIT} 个字符")
    return signed_by, note


def list_cases(db: Session) -> list[Case]:
    return (
        db.query(Case)
        .options(selectinload(Case.runs).selectinload(AnalysisRun.artifacts))
        .order_by(Case.updated_at.desc(), Case.id.desc())
        .all()
    )


def create_case(db: Session, data: dict[str, Any]) -> Case:
    normalized = normalize_case_data(data)
    case = Case(
        title=normalized["title"],
        db_type=normalized["db_type"],
        target_system=normalized["target_system"],
        change_type=normalized["change_type"],
        priority=normalized["priority"],
        environment=normalized["environment"],
        owner=normalized["owner"],
        approver=normalized["approver"],
        planned_window=normalized["planned_window"],
        business_context=normalized["business_context"],
        source_sql=normalized["source_sql"],
        schema_notes=normalized["schema_notes"],
        constraints=normalized["constraints"],
        status="draft",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def get_case(db: Session, case_id: int) -> Case | None:
    return (
        db.query(Case)
        .options(
            selectinload(Case.runs)
            .selectinload(AnalysisRun.artifacts)
            .selectinload(Artifact.revisions),
            selectinload(Case.runs).selectinload(AnalysisRun.llm_logs),
        )
        .filter(Case.id == case_id)
        .first()
    )


def get_run(db: Session, run_id: int) -> AnalysisRun | None:
    return (
        db.query(AnalysisRun)
        .options(
            selectinload(AnalysisRun.artifacts).selectinload(Artifact.revisions),
            selectinload(AnalysisRun.llm_logs),
            selectinload(AnalysisRun.case),
        )
        .filter(AnalysisRun.id == run_id)
        .first()
    )


def get_artifact_with_revisions(db: Session, artifact_id: int) -> Artifact | None:
    return (
        db.query(Artifact)
        .options(selectinload(Artifact.revisions))
        .filter(Artifact.id == artifact_id)
        .first()
    )


def artifact_content_diff(artifact: Artifact | None) -> dict[str, Any]:
    revisions = sorted(artifact.revisions, key=lambda revision: revision.version) if artifact else []
    pair: tuple[ArtifactRevision, ArtifactRevision] | None = None
    for previous, current in zip(revisions, revisions[1:]):
        if previous.content != current.content:
            pair = (previous, current)
    if not pair:
        return {
            "available": False,
            "state_label": "暂无可对比的内容变化",
            "from_version": None,
            "to_version": None,
            "additions": 0,
            "deletions": 0,
            "lines": [],
        }
    previous, current = pair
    diff_lines = list(
        difflib.unified_diff(
            previous.content.splitlines(),
            current.content.splitlines(),
            fromfile=f"v{previous.version} {event_label(previous.event)}",
            tofile=f"v{current.version} {event_label(current.event)}",
            lineterm="",
        )
    )
    display_lines: list[dict[str, str]] = []
    additions = 0
    deletions = 0
    for line in diff_lines:
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("+"):
            additions += 1
            display_lines.append({"kind": "add", "text": line[1:]})
        elif line.startswith("-"):
            deletions += 1
            display_lines.append({"kind": "del", "text": line[1:]})
        else:
            display_lines.append({"kind": "ctx", "text": line[1:] if line.startswith(" ") else line})
    return {
        "available": True,
        "state_label": f"v{previous.version} 到 v{current.version} 的内容变化",
        "from_version": previous.version,
        "from_event": previous.event,
        "from_event_label": event_label(previous.event),
        "to_version": current.version,
        "to_event": current.event,
        "to_event_label": event_label(current.event),
        "additions": additions,
        "deletions": deletions,
        "lines": display_lines[:80],
    }


def delivery_summary(run: AnalysisRun | None) -> dict[str, Any]:
    artifacts = list(run.artifacts) if run else []
    total = len(artifacts)
    approved = sum(1 for artifact in artifacts if artifact.status == "approved")
    pending_titles = [
        artifact.title for artifact in artifacts if artifact.status != "approved"
    ]
    pending = total - approved
    percent = int(round((approved / total) * 100)) if total else 0
    is_complete = total > 0 and pending == 0
    return {
        "total": total,
        "approved": approved,
        "pending": pending,
        "percent": percent,
        "is_complete": is_complete,
        "label": f"{approved}/{total} 已确认" if total else "暂无交付物",
        "state_label": "交付包已确认，可导出" if is_complete else f"还有 {pending} 项待确认",
        "pending_titles": pending_titles,
    }


def run_signoff_summary(run: AnalysisRun | None) -> dict[str, Any]:
    status = run.signoff_status if run else "pending"
    is_signed = status == "signed"
    return {
        "status": status,
        "label": "已签收" if is_signed else "待签收",
        "is_signed": is_signed,
        "signed_by": run.signed_by if run and run.signed_by else "",
        "signoff_note": run.signoff_note if run and run.signoff_note else "",
        "signed_at": format_dt(run.signed_at) if run else "-",
    }


def workbench_summary(cases: list[Case]) -> dict[str, Any]:
    runs = [run for case in cases for run in case.runs]
    artifacts = [artifact for run in runs for artifact in run.artifacts]
    latest_run = max(runs, key=lambda run: run.id, default=None)
    approved_artifacts = sum(1 for artifact in artifacts if artifact.status == "approved")
    signed_runs = sum(1 for run in runs if run.signoff_status == "signed")
    fallback_runs = sum(1 for run in runs if run.provider == "fixture" or run.model == "offline-demo")
    ready_cases = sum(1 for case in cases if case.runs)
    signed_label = f"{signed_runs}/{len(runs)} 个交付包已签收" if runs else "暂无签收记录"
    return {
        "total_cases": len(cases),
        "ready_cases": ready_cases,
        "total_runs": len(runs),
        "total_artifacts": len(artifacts),
        "approved_artifacts": approved_artifacts,
        "signed_runs": signed_runs,
        "fallback_runs": fallback_runs,
        "latest_run": latest_run,
        "latest_delivery": delivery_summary(latest_run),
        "latest_signoff": run_signoff_summary(latest_run),
        "signed_label": signed_label,
        "ready_label": f"{ready_cases}/{len(cases)} 个案例已有方案" if cases else "暂无案例",
        "artifact_label": (
            f"{approved_artifacts}/{len(artifacts)} 份交付物已确认"
            if artifacts
            else "暂无交付物"
        ),
    }


def _database_label(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        return "SQLite 本地数据库"
    return url.render_as_string(hide_password=True)


def operational_status(cases: list[Case], settings: BaseModel, database_ok: bool = True) -> dict[str, Any]:
    summary = workbench_summary(cases)
    latest_run = summary["latest_run"]
    public_summary = dict(summary)
    public_summary["latest_run"] = latest_run.id if latest_run else None
    has_seed_cases = len(cases) >= 5
    has_ready_case = summary["ready_cases"] > 0
    has_signed_run = summary["signed_runs"] > 0
    llm_configured = bool(getattr(settings, "llm_api_key", ""))
    checks = [
        {
            "name": "数据库连接",
            "state": "ok" if database_ok else "error",
            "label": "可连接" if database_ok else "连接失败",
        },
        {
            "name": "合成案例",
            "state": "ok" if has_seed_cases else "warning",
            "label": f"{len(cases)} 个案例",
        },
        {
            "name": "交付方案",
            "state": "ok" if has_ready_case else "warning",
            "label": summary["ready_label"],
        },
        {
            "name": "交付签收",
            "state": "ok" if has_signed_run else "warning",
            "label": summary["signed_label"],
        },
        {
            "name": "模型模式",
            "state": "ok" if llm_configured else "warning",
            "label": "真实模型已配置" if llm_configured else "离线兜底可用",
        },
    ]
    next_actions: list[dict[str, str]] = []
    if not database_ok:
        next_actions.append(
            {
                "level": "error",
                "title": "修复数据库连接",
                "detail": "检查 DATABASE_URL、数据库权限和网络连通性，先让 /healthz 返回 ok。",
                "href": "/healthz",
                "cta": "查看健康检查",
            }
        )
    if database_ok and not has_seed_cases:
        next_actions.append(
            {
                "level": "warning",
                "title": "恢复合成演示案例",
                "detail": "确认应用启动流程已执行数据初始化，或重新部署服务以写入 5 个内置 DBA 场景。",
                "href": "/",
                "cta": "查看案例库",
            }
        )
    if database_ok and has_seed_cases and not has_ready_case:
        next_actions.append(
            {
                "level": "warning",
                "title": "生成首份交付方案",
                "detail": "进入演示台点击“一键生成交付包”，验证 AI 分析、兜底和交付物生成链路。",
                "href": "/demo",
                "cta": "打开演示台",
            }
        )
    if database_ok and has_seed_cases and not has_signed_run:
        next_actions.append(
            {
                "level": "warning",
                "title": "完成一份签收闭环",
                "detail": "点击“一键完整闭环”或手动确认 6 类交付物后签收，证明复核、确认、签收和导出链路可用。",
                "href": "/demo",
                "cta": "完成演示闭环",
            }
        )
    if not llm_configured:
        next_actions.append(
            {
                "level": "info",
                "title": "按需接入真实模型",
                "detail": "当前离线兜底适合稳定演示；需要展示真实模型调用时，配置 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL。",
                "href": "/ops",
                "cta": "查看配置状态",
            }
        )
    if not next_actions:
        next_actions.append(
            {
                "level": "ok",
                "title": "保持发布前验证",
                "detail": "运行 release_readiness 和线上冒烟检查，确认代码、样例交付包和公开材料仍然完整。",
                "href": "/api/system/status",
                "cta": "查看状态 JSON",
            }
        )
    is_ready = database_ok and has_seed_cases
    return {
        "service": "dba-changeops-ai-workbench",
        "app_env": getattr(settings, "app_env", "development"),
        "database": _database_label(getattr(settings, "database_url", "")),
        "database_ok": database_ok,
        "llm_base_url": getattr(settings, "llm_base_url", ""),
        "llm_model": getattr(settings, "llm_model", ""),
        "llm_configured": llm_configured,
        "llm_mode_label": "真实模型" if llm_configured else "离线兜底",
        "readiness_label": "可交付试运行" if is_ready else "需要补齐配置",
        "ready": is_ready,
        "summary": public_summary,
        "checks": checks,
        "next_actions": next_actions,
        "latest_run_id": latest_run.id if latest_run else None,
    }


def _next_artifact_version(db: Session, artifact_id: int) -> int:
    latest = (
        db.query(func.max(ArtifactRevision.version))
        .filter(ArtifactRevision.artifact_id == artifact_id)
        .scalar()
    )
    return int(latest or 0) + 1


def _record_artifact_revision(db: Session, artifact: Artifact, event: str) -> None:
    db.add(
        ArtifactRevision(
            artifact_id=artifact.id,
            run_id=artifact.run_id,
            version=_next_artifact_version(db, artifact.id),
            event=event,
            content=artifact.content,
            status=artifact.status,
        )
    )


def analyze_case(db: Session, case: Case, client: LLMClient | None = None) -> AnalysisRun:
    run = AnalysisRun(case_id=case.id, status="running", provider="pending", model="pending")
    db.add(run)
    db.commit()
    db.refresh(run)

    client = client or LLMClient()
    result = client.analyze_change(case)

    run.provider = result.provider
    run.model = result.model
    run.status = "completed" if result.status in {"success", "fallback"} else "failed"
    run.summary = result.data["summary"]
    run.error_message = result.error_message
    run.completed_at = utc_now()

    db.add(
        LLMCallLog(
            run_id=run.id,
            provider=result.provider,
            model=result.model,
            status=result.status,
            latency_ms=result.latency_ms,
            request_payload=result.request_payload,
            response_payload=result.response_payload,
            error_message=result.error_message,
        )
    )

    for artifact_type, title in ARTIFACT_TITLES.items():
        artifact = Artifact(
            case_id=case.id,
            run_id=run.id,
            artifact_type=artifact_type,
            title=title,
            content=result.data["artifacts"][artifact_type],
            status="draft",
        )
        db.add(artifact)
        db.flush()
        _record_artifact_revision(db, artifact, "generated")

    case.status = "analysis_ready"
    case.updated_at = utc_now()
    db.commit()
    db.refresh(run)
    return run


def approve_artifact(db: Session, artifact_id: int) -> Artifact | None:
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        return None
    already_approved = artifact.status == "approved"
    artifact.status = "approved"
    artifact.approved_at = utc_now()
    artifact.updated_at = utc_now()
    if not already_approved:
        _record_artifact_revision(db, artifact, "approved")
    db.commit()
    db.refresh(artifact)
    return artifact


def approve_run_artifacts(db: Session, run_id: int) -> AnalysisRun | None:
    run = get_run(db, run_id)
    if not run:
        return None
    now = utc_now()
    for artifact in run.artifacts:
        if artifact.status == "approved":
            continue
        artifact.status = "approved"
        artifact.approved_at = now
        artifact.updated_at = now
        _record_artifact_revision(db, artifact, "approved")
    if run.artifacts:
        run.artifacts[0].case.updated_at = now
    db.commit()
    db.refresh(run)
    return run


def signoff_run(db: Session, run_id: int, signed_by: str = "", note: str = "") -> AnalysisRun | None:
    run = get_run(db, run_id)
    if not run:
        return None
    delivery = delivery_summary(run)
    if not delivery["is_complete"]:
        raise ValueError("交付物全部确认后才能签收")
    signed_by, note = normalize_signoff_input(signed_by, note)
    now = utc_now()
    run.signoff_status = "signed"
    run.signed_by = signed_by or run.case.approver or run.case.owner or "变更审批人"
    run.signoff_note = note
    run.signed_at = now
    run.case.updated_at = now
    db.commit()
    db.refresh(run)
    return run


def update_artifact_content(db: Session, artifact_id: int, content: str) -> Artifact | None:
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        return None
    next_content = normalize_artifact_content(content)
    should_record = (
        next_content != artifact.content or artifact.status != "draft" or artifact.approved_at is not None
    )
    artifact.content = next_content
    artifact.status = "draft"
    artifact.approved_at = None
    artifact.updated_at = utc_now()
    artifact.case.updated_at = utc_now()
    artifact.run.signoff_status = "pending"
    artifact.run.signed_by = ""
    artifact.run.signoff_note = ""
    artifact.run.signed_at = None
    if should_record:
        _record_artifact_revision(db, artifact, "edited")
    db.commit()
    db.refresh(artifact)
    return artifact


def format_dt(value) -> str:
    if not value:
        return "-"
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def status_label(value: str | None) -> str:
    if not value:
        return "-"
    return STATUS_LABELS.get(value, value)


def provider_label(value: str | None) -> str:
    if not value:
        return "-"
    return PROVIDER_LABELS.get(value, value)


def event_label(value: str | None) -> str:
    if not value:
        return "-"
    return EVENT_LABELS.get(value, value)
