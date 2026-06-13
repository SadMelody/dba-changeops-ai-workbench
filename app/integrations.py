from __future__ import annotations

import json
from typing import Any

import httpx

from app.services import delivery_summary, format_dt, provider_label, run_signoff_summary, status_label


WORK_ORDER_FIELD_LABELS = {
    "external_id": "外部工单号",
    "title": "标题",
    "database_type": "数据库类型",
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

WORK_ORDER_ID_PREFIX = "外部工单："
WORK_ORDER_URL_PREFIX = "工单链接："
WORK_ORDER_LABELS_PREFIX = "工单标签："


def _text(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key not in data:
            continue
        value = data[key]
        if value is None:
            continue
        if not isinstance(value, str):
            label = WORK_ORDER_FIELD_LABELS.get(key, key)
            raise ValueError(f"{label}必须是文本")
        value = value.strip()
        if value:
            return value
    return default


def _bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key, False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        raise ValueError(f"{key}必须是字符串数组")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{key}必须是字符串数组")
        item = item.strip()
        if item:
            items.append(item)
    return items


def _metadata_lines(metadata: Any) -> list[str]:
    if metadata in (None, ""):
        return []
    if not isinstance(metadata, dict):
        raise ValueError("metadata 必须是 JSON 对象")
    lines: list[str] = []
    for key in sorted(metadata):
        value = metadata[key]
        if value in (None, ""):
            continue
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        lines.append(f"- {key}: {rendered}")
    return lines


def _combine_sections(*sections: str) -> str:
    return "\n\n".join(section.strip() for section in sections if section and section.strip())


def _operation_text(data: dict[str, Any]) -> str:
    direct = _text(data, "source_sql", "sql", "change_script", "script")
    if direct:
        return direct
    commands = _string_list(data, "operation_commands")
    return "\n".join(commands)


def normalize_work_order_payload(data: dict[str, Any]) -> dict[str, Any]:
    external_id = _text(data, "external_id", "ticket_id", "change_id")
    title = _text(data, "title", "summary")
    if not external_id:
        raise ValueError("外部工单号不能为空")
    if not title:
        raise ValueError("标题不能为空")

    labels = _string_list(data, "labels")
    metadata = _metadata_lines(data.get("metadata"))
    external_url = _text(data, "external_url", "ticket_url", "url")

    source_header = [f"外部工单：{external_id}"]
    if external_url:
        source_header.append(f"工单链接：{external_url}")
    if labels:
        source_header.append(f"工单标签：{', '.join(labels)}")
    if metadata:
        source_header.append("工单元数据：\n" + "\n".join(metadata))

    business_context = _combine_sections(
        "\n".join(source_header),
        _text(data, "business_context", "description", "background"),
    )
    schema_notes = _combine_sections(
        _text(data, "schema_notes", "schema", "affected_objects"),
        _text(data, "impact", "impact_scope"),
    )
    constraints = _combine_sections(
        _text(data, "constraints", "risk_constraints"),
        _text(data, "rollback_requirement", "rollback_required"),
    )

    case_data = {
        "title": title,
        "db_type": _text(data, "db_type", "database_type", default="DB2"),
        "target_system": _text(data, "target_system", "system"),
        "change_type": _text(data, "change_type", "category", default="数据库变更"),
        "priority": _text(data, "priority", default="P2"),
        "environment": _text(data, "environment", "env"),
        "owner": _text(data, "owner", "requester"),
        "approver": _text(data, "approver", "approval_owner"),
        "planned_window": _text(data, "planned_window", "window"),
        "business_context": business_context,
        "source_sql": _operation_text(data),
        "schema_notes": schema_notes,
        "constraints": constraints,
    }
    return {
        "case_data": case_data,
        "source": {
            "external_id": external_id,
            "external_url": external_url,
            "labels": labels,
        },
        "run_analysis": _bool(data, "run_analysis"),
    }


def extract_work_order_reference(case: Any) -> dict[str, Any]:
    reference = {
        "external_id": "",
        "external_url": "",
        "labels": [],
    }
    business_context = getattr(case, "business_context", "") or ""
    for raw_line in business_context.splitlines():
        line = raw_line.strip()
        if line.startswith(WORK_ORDER_ID_PREFIX):
            reference["external_id"] = line.removeprefix(WORK_ORDER_ID_PREFIX).strip()
        elif line.startswith(WORK_ORDER_URL_PREFIX):
            reference["external_url"] = line.removeprefix(WORK_ORDER_URL_PREFIX).strip()
        elif line.startswith(WORK_ORDER_LABELS_PREFIX):
            labels = line.removeprefix(WORK_ORDER_LABELS_PREFIX).strip()
            reference["labels"] = [label.strip() for label in labels.split(",") if label.strip()]
    return reference


def _absolute_url(base_url: str, path: str) -> str:
    if not base_url:
        return path
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _writeback_status(run: Any, signoff: dict[str, Any], delivery: dict[str, Any]) -> str:
    if signoff["is_signed"]:
        return "signed"
    if delivery["is_complete"]:
        return "ready_for_signoff"
    if getattr(run, "status", "") == "completed":
        return "delivery_generated"
    return getattr(run, "status", "unknown") or "unknown"


def build_work_order_writeback_payload(run: Any, base_url: str = "") -> dict[str, Any]:
    case = run.case
    source = extract_work_order_reference(case)
    if not source["external_id"]:
        raise ValueError("当前分析运行没有关联外部工单")

    delivery = delivery_summary(run)
    signoff = run_signoff_summary(run)
    status = _writeback_status(run, signoff, delivery)
    run_path = f"/cases/{case.id}/runs/{run.id}"
    markdown_path = f"{run_path}/export"
    pdf_path = f"{run_path}/export.pdf"

    comment_lines = [
        f"DBA ChangeOps 已生成交付包：{case.title}",
        f"- 交付状态：{delivery['label']}（{delivery['percent']}%）",
        f"- 签收状态：{signoff['label']}",
        f"- 分析来源：{provider_label(run.provider)} / {provider_label(run.model)}",
        f"- 交付包：{_absolute_url(base_url, run_path)}",
        f"- Markdown：{_absolute_url(base_url, markdown_path)}",
        f"- PDF：{_absolute_url(base_url, pdf_path)}",
    ]
    if signoff["is_signed"]:
        comment_lines.append(f"- 签收人：{signoff['signed_by']}，签收时间：{signoff['signed_at']}")
    if delivery["pending_titles"]:
        comment_lines.append("- 待确认项：" + "、".join(delivery["pending_titles"]))

    return {
        "action": "work_order_delivery_writeback",
        "source": source,
        "target_status": status,
        "case": {
            "id": case.id,
            "title": case.title,
            "status": case.status,
            "status_label": status_label(case.status),
            "priority": case.priority,
            "environment": case.environment,
            "owner": case.owner,
            "approver": case.approver,
            "planned_window": case.planned_window,
            "url": _absolute_url(base_url, f"/cases/{case.id}"),
        },
        "run": {
            "id": run.id,
            "status": run.status,
            "status_label": status_label(run.status),
            "provider": run.provider,
            "provider_label": provider_label(run.provider),
            "model": run.model,
            "model_label": provider_label(run.model),
            "completed_at": format_dt(run.completed_at),
            "summary": run.summary,
            "url": _absolute_url(base_url, run_path),
        },
        "delivery": delivery,
        "signoff": signoff,
        "exports": {
            "markdown": _absolute_url(base_url, markdown_path),
            "pdf": _absolute_url(base_url, pdf_path),
        },
        "artifacts": [
            {
                "type": artifact.artifact_type,
                "title": artifact.title,
                "status": artifact.status,
                "status_label": status_label(artifact.status),
                "approved_at": format_dt(artifact.approved_at),
            }
            for artifact in run.artifacts
        ],
        "comment_markdown": "\n".join(comment_lines),
    }


def _response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:2000]


def dispatch_work_order_writeback(
    payload: dict[str, Any],
    settings: Any,
    *,
    http_client_factory: Any = httpx.Client,
    timeout: float = 10,
) -> dict[str, Any]:
    webhook_url = (getattr(settings, "itsm_webhook_url", "") or "").strip()
    if not webhook_url:
        raise ValueError("ITSM_WEBHOOK_URL 未配置，无法主动回写工单")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "dba-changeops-ai-workbench/1.0",
    }
    token = (getattr(settings, "itsm_webhook_token", "") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with http_client_factory(timeout=timeout) as client:
            response = client.post(webhook_url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"ITSM Webhook 回写失败：{exc}") from exc

    body = _response_body(response)
    if response.status_code >= 400:
        raise RuntimeError(f"ITSM Webhook 回写失败：HTTP {response.status_code}")

    return {
        "configured": True,
        "url": webhook_url,
        "status_code": response.status_code,
        "accepted": True,
        "response": body,
    }
