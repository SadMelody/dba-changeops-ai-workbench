from __future__ import annotations

import textwrap

from app.models import Artifact, Case
from app.services import (
    artifact_content_diff,
    delivery_summary,
    event_label,
    format_dt,
    provider_label,
    run_signoff_summary,
    status_label,
)

PDF_LINE_WIDTH = 72
PDF_ROWS_PER_PAGE = 42


def _latest_run(case: Case):
    return case.runs[0] if case.runs else None


def _document_id(case: Case) -> str:
    latest_run = _latest_run(case)
    suffix = f"RUN-{latest_run.id:04d}" if latest_run else "DRAFT"
    return f"CHANGEOPS-{case.id:04d}-{suffix}"


def _artifact_titles(run) -> list[str]:
    return [artifact.title for artifact in run.artifacts] if run else []


def _llm_audit_summary(run) -> str:
    if not run or not run.llm_logs:
        return "暂无 LLM 调用记录"
    latest_log = run.llm_logs[0]
    return (
        f"{len(run.llm_logs)} 条调用记录；最新状态：{status_label(latest_log.status)}；"
        f"来源：{provider_label(latest_log.provider)} / {provider_label(latest_log.model)}"
    )


def _artifact_revision_lines(artifact: Artifact) -> list[str]:
    if not artifact.revisions:
        return ["- 暂无版本记录"]
    revisions = sorted(artifact.revisions, key=lambda revision: revision.version)
    return [
        (
            f"- v{revision.version}：{event_label(revision.event)} / "
            f"{status_label(revision.status)} / {format_dt(revision.created_at)}"
        )
        for revision in revisions
    ]


def _artifact_diff_summary(artifact: Artifact) -> str:
    diff = artifact_content_diff(artifact)
    if not diff["available"]:
        return "最近内容变化：暂无可对比的内容变化"
    return (
        f"最近内容变化：{diff['state_label']}，"
        f"新增 {diff['additions']} 行，删除 {diff['deletions']} 行"
    )


def export_markdown(case: Case) -> str:
    latest_run = _latest_run(case)
    delivery = delivery_summary(latest_run)
    signoff = run_signoff_summary(latest_run)
    artifact_titles = _artifact_titles(latest_run)
    lines = [
        "# DBA ChangeOps AI 变更交付包",
        "",
        "## 文档封面",
        "",
        f"- 文档编号：{_document_id(case)}",
        f"- 案例名称：{case.title}",
        "- 文档用途：变更评审、执行前沟通、交付存档",
        "- 数据来源：合成 DBA 运维案例，不包含真实生产数据",
        f"- 环境：{case.environment or '-'}",
        f"- 负责人：{case.owner or '-'}",
        f"- 审批人：{case.approver or '-'}",
        f"- 计划窗口：{case.planned_window or '-'}",
        f"- 生成时间：{format_dt(latest_run.completed_at) if latest_run else '-'}",
        f"- 交付结论：{delivery['state_label']}",
        f"- 签收状态：{signoff['label']}",
        f"- 审计摘要：{_llm_audit_summary(latest_run)}",
        "",
        "## 目录",
        "",
        "- 变更元数据",
        "- 原始需求",
        "- 交付完成度",
        "- AI 摘要",
        "- 交付清单",
        "- 交付物正文与版本记录",
        "- LLM 调用审计",
        "",
        "## 变更元数据",
        "",
        f"- 数据库：{case.db_type}",
        f"- 目标系统：{case.target_system}",
        f"- 变更类型：{case.change_type}",
        f"- 优先级：{case.priority}",
        f"- 环境：{case.environment or '-'}",
        f"- 负责人：{case.owner or '-'}",
        f"- 审批人：{case.approver or '-'}",
        f"- 计划窗口：{case.planned_window or '-'}",
        f"- 状态：{status_label(case.status)}",
        f"- 文档编号：{_document_id(case)}",
        "",
        "## 原始需求",
        "",
        case.business_context or "-",
        "",
        "```sql",
        case.source_sql or "-- 未提供 SQL",
        "```",
        "",
        "## 表结构说明",
        "",
        case.schema_notes or "-",
        "",
        "## 约束条件",
        "",
        case.constraints or "-",
        "",
    ]

    if latest_run:
        lines += [
            "## 交付完成度",
            "",
            f"- 完成度：{delivery['label']}",
            f"- 当前状态：{delivery['state_label']}",
            f"- 签收状态：{signoff['label']}",
            f"- 交付物数量：{delivery['total']} 份",
        ]
        if signoff["is_signed"]:
            lines += [
                f"- 签收人：{signoff['signed_by']}",
                f"- 签收时间：{signoff['signed_at']}",
            ]
            if signoff["signoff_note"]:
                lines += [f"- 签收说明：{signoff['signoff_note']}"]
        if delivery["pending_titles"]:
            lines += [f"- 待确认交付物：{'、'.join(delivery['pending_titles'])}"]
        lines += ["", "## AI 摘要", "", latest_run.summary, ""]
        lines += ["## 交付清单", ""]
        for artifact in latest_run.artifacts:
            lines += [
                (
                    f"- {artifact.title}：{status_label(artifact.status)}，"
                    f"最近更新 {format_dt(artifact.updated_at)}，"
                    f"确认时间 {format_dt(artifact.approved_at)}"
                )
            ]
        lines += [""]
        for artifact in latest_run.artifacts:
            lines += [
                f"## {artifact.title}",
                "",
                f"- 交付状态：{status_label(artifact.status)}",
                f"- 最近更新：{format_dt(artifact.updated_at)}",
                f"- 确认时间：{format_dt(artifact.approved_at)}",
                "",
                artifact.content,
                "",
                "### 版本记录",
                "",
                *_artifact_revision_lines(artifact),
                "",
                f"- {_artifact_diff_summary(artifact)}",
                "",
            ]
        lines += ["## LLM 调用审计", ""]
        if latest_run.llm_logs:
            for log in latest_run.llm_logs:
                lines += [
                    (
                        f"- {format_dt(log.created_at)}：{provider_label(log.provider)} / "
                        f"{provider_label(log.model)} / {status_label(log.status)} / "
                        f"{log.latency_ms} ms"
                    )
                ]
                if log.error_message:
                    lines += [f"  - 失败原因：{log.error_message}"]
        else:
            lines += ["- 暂无 LLM 调用记录"]
        lines += [""]
    elif artifact_titles:
        lines += ["## 交付清单", "", f"- {'、'.join(artifact_titles)}", ""]
    return "\n".join(lines)


def _append_pdf_block(rows: list[str], text: str) -> None:
    for raw_line in str(text or "-").replace("\r", "").splitlines() or ["-"]:
        if not raw_line:
            rows.append("")
            continue
        rows.extend(textwrap.wrap(raw_line, width=PDF_LINE_WIDTH) or [""])


def _pdf_document_rows(case: Case) -> list[str]:
    latest_run = _latest_run(case)
    delivery = delivery_summary(latest_run)
    signoff = run_signoff_summary(latest_run)
    rows: list[str] = [
        "DBA ChangeOps AI 变更交付包",
        "=" * 38,
        "文档封面",
        "-" * 24,
        f"文档编号：{_document_id(case)}",
        f"案例：{case.title}",
        "文档用途：变更评审、执行前沟通、交付存档",
        "数据来源：合成 DBA 运维案例，不包含真实生产数据",
        f"数据库：{case.db_type}",
        f"目标系统：{case.target_system}",
        f"变更类型：{case.change_type}",
        f"优先级：{case.priority}",
        f"环境：{case.environment or '-'}",
        f"负责人：{case.owner or '-'}",
        f"审批人：{case.approver or '-'}",
        f"计划窗口：{case.planned_window or '-'}",
        f"案例状态：{status_label(case.status)}",
        f"生成时间：{format_dt(latest_run.completed_at) if latest_run else '-'}",
        f"交付结论：{delivery['state_label']}",
        f"签收状态：{signoff['label']}",
        f"审计摘要：{_llm_audit_summary(latest_run)}",
        "",
        "目录",
        "-" * 24,
        "一、原始变更需求",
        "二、AI 交付概览",
        "三、交付物状态总览",
        "四、交付物正文",
        "五、LLM 调用审计",
        "六、交付说明",
        "",
        "一、原始变更需求",
        "-" * 24,
    ]
    _append_pdf_block(rows, case.business_context or "-")
    rows += ["", "SQL / 操作命令："]
    _append_pdf_block(rows, case.source_sql or "-- 未提供 SQL")
    rows += ["", "表结构说明："]
    _append_pdf_block(rows, case.schema_notes or "-")
    rows += ["", "约束条件："]
    _append_pdf_block(rows, case.constraints or "-")

    if not latest_run:
        rows += ["", "二、交付包状态", "-" * 24, "暂无分析记录。"]
        return rows

    rows += [
        "",
        "二、AI 交付概览",
        "-" * 24,
        f"分析记录：第 {latest_run.id} 次",
        f"生成来源：{provider_label(latest_run.provider)} / {provider_label(latest_run.model)}",
        f"分析状态：{status_label(latest_run.status)}",
        f"交付完成度：{delivery['label']}",
        f"交付状态：{delivery['state_label']}",
        f"签收状态：{signoff['label']}",
        f"交付物数量：{delivery['total']} 份",
    ]
    if signoff["is_signed"]:
        rows += [
            f"签收人：{signoff['signed_by']}",
            f"签收时间：{signoff['signed_at']}",
        ]
        if signoff["signoff_note"]:
            _append_pdf_block(rows, f"签收说明：{signoff['signoff_note']}")
    if latest_run.error_message:
        rows.append(f"失败原因：{latest_run.error_message}")
    if delivery["pending_titles"]:
        _append_pdf_block(rows, f"待确认交付物：{'、'.join(delivery['pending_titles'])}")
    _append_pdf_block(rows, f"摘要：{latest_run.summary}")

    rows += ["", "三、交付物状态总览", "-" * 24]
    for artifact in latest_run.artifacts:
        rows.append(
            f"- {artifact.title}：{status_label(artifact.status)}，"
            f"更新 {format_dt(artifact.updated_at)}，确认 {format_dt(artifact.approved_at)}"
        )

    rows += ["", "四、交付物正文", "-" * 24]
    for index, artifact in enumerate(latest_run.artifacts, start=1):
        rows += [
            "",
            f"4.{index} {artifact.title}",
            f"交付状态：{status_label(artifact.status)}",
            f"最近更新：{format_dt(artifact.updated_at)}",
            f"确认时间：{format_dt(artifact.approved_at)}",
            "正文：",
        ]
        _append_pdf_block(rows, artifact.content)
        rows.append("版本记录：")
        rows.extend(_artifact_revision_lines(artifact))
        rows.append(_artifact_diff_summary(artifact))

    rows += ["", "五、LLM 调用审计", "-" * 24]
    if latest_run.llm_logs:
        for log in latest_run.llm_logs:
            rows.append(
                f"- {format_dt(log.created_at)}：{provider_label(log.provider)} / "
                f"{provider_label(log.model)} / {status_label(log.status)} / {log.latency_ms} ms"
            )
            if log.error_message:
                _append_pdf_block(rows, f"失败原因：{log.error_message}")
    else:
        rows.append("- 暂无 LLM 调用记录")

    rows += [
        "",
        "六、交付说明",
        "-" * 24,
        "本文件由 DBA ChangeOps AI 工作台生成，适用于变更评审、执行前沟通和交付存档。",
        "正式生产执行前仍需要 DBA、应用负责人和变更审批人复核确认。",
    ]
    return rows


def export_pdf_bytes(case: Case) -> bytes:
    rows = _pdf_document_rows(case)
    pages = [rows[i : i + PDF_ROWS_PER_PAGE] for i in range(0, len(rows), PDF_ROWS_PER_PAGE)] or [[]]
    objects: dict[int, str] = {}
    catalog_id = 1
    pages_id = 2
    font_id = 3
    cid_font_id = 4
    next_id = 5
    page_ids: list[int] = []

    objects[catalog_id] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
    objects[font_id] = (
        f"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
        f"/Encoding /UniGB-UCS2-H /DescendantFonts [{cid_font_id} 0 R] >>"
    )
    objects[cid_font_id] = (
        "<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> >>"
    )

    total_pages = len(pages)
    for page_number, page in enumerate(pages, start=1):
        stream_lines = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        header = f"DBA ChangeOps AI 工作台 · {case.title}"
        header_hex = header.encode("utf-16-be", "ignore").hex().upper()
        stream_lines.append(f"<{header_hex}> Tj")
        stream_lines.append("T*")
        stream_lines.append("T*")
        for line in page:
            hex_text = line.encode("utf-16-be", "ignore").hex().upper()
            stream_lines.append(f"<{hex_text}> Tj")
            stream_lines.append("T*")
        footer = f"第 {page_number} / {total_pages} 页 · 生成于 {format_dt(case.updated_at)}"
        footer_hex = footer.encode("utf-16-be", "ignore").hex().upper()
        stream_lines.extend(["ET", "BT", "/F1 9 Tf", "50 34 Td", f"<{footer_hex}> Tj"])
        stream_lines.append("ET")
        stream = "\n".join(stream_lines)
        content_id = next_id
        next_id += 1
        page_id = next_id
        next_id += 1
        objects[content_id] = (
            f"<< /Length {len(stream.encode('ascii', 'ignore'))} >>\n"
            f"stream\n{stream}\nendstream"
        )
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    pdf = ["%PDF-1.4\n"]
    offsets: dict[int, int] = {}
    max_id = max(objects)
    for idx in range(1, max_id + 1):
        body = objects[idx]
        offsets[idx] = sum(len(part.encode("ascii", "ignore")) for part in pdf)
        pdf.append(f"{idx} 0 obj\n{body}\nendobj\n")
    xref_at = sum(len(part.encode("ascii", "ignore")) for part in pdf)
    pdf.append(f"xref\n0 {max_id + 1}\n0000000000 65535 f \n")
    for idx in range(1, max_id + 1):
        pdf.append(f"{offsets[idx]:010d} 00000 n \n")
    pdf.append(
        f"trailer\n<< /Size {max_id + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF"
    )
    return "".join(pdf).encode("ascii", "ignore")
