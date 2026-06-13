from __future__ import annotations

import json
import os
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LLM_API_KEY"] = ""

import httpx
from fastapi.testclient import TestClient

from app.config import load_dotenv
from app.database import Base, SessionLocal, engine
from app.demo_data import ARTIFACT_TITLES, DEMO_CASES, fixture_analysis
from app.llm import LLMClient, normalize_response, sanitize_audit_payload
from app.main import app
from app.models import Artifact, ArtifactRevision, Case


def pdf_contains(pdf: bytes, text: str) -> bool:
    return text.encode("utf-16-be").hex().upper().encode() in pdf


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def make_case() -> Case:
    return Case(
        title="DB2 LLM adapter test",
        db_type="DB2 LUW",
        target_system="核心账务",
        change_type="在线索引变更",
        priority="P2",
        business_context="测试 LLM 适配层的成功和兜底路径。",
        source_sql="CREATE INDEX IX_TEST ON APP.T(ID);",
        schema_notes="合成表结构。",
        constraints="维护窗口较短。",
    )


def make_settings(api_key: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        llm_base_url="https://llm.example.test/v1",
        llm_api_key=api_key,
        llm_model="qwen-plus",
    )


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "mock provider failed",
                request=httpx.Request("POST", "https://llm.example.test/v1/chat/completions"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self.payload


class FakeHTTPClient:
    last_request: dict | None = None

    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    def __enter__(self) -> "FakeHTTPClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        FakeHTTPClient.last_request = {"url": url, "headers": headers, "json": json}
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def test_normalize_response_fills_missing_structured_artifacts() -> None:
    case = make_case()

    normalized = normalize_response(
        {
            "summary": "模型返回的摘要",
            "artifacts": {
                "risk_assessment": "模型返回的风险评估",
            },
        },
        case,
    )

    assert normalized["summary"] == "模型返回的摘要"
    assert normalized["artifacts"]["risk_assessment"] == "模型返回的风险评估"
    assert set(normalized["artifacts"]) == set(ARTIFACT_TITLES)
    assert normalized["artifacts"]["runbook"]
    assert normalized["artifacts"]["rollback_plan"]


def test_load_dotenv_reads_local_env_without_overriding_existing_values(
    tmp_path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# local demo config",
                "LLM_MODEL=qwen-plus",
                "LLM_API_KEY=from-file",
                "APP_ENV='development'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "from-shell")
    monkeypatch.delenv("APP_ENV", raising=False)

    load_dotenv(env_file)

    assert os.environ["LLM_MODEL"] == "qwen-plus"
    assert os.environ["LLM_API_KEY"] == "from-shell"
    assert os.environ["APP_ENV"] == "development"


def test_sanitize_audit_payload_redacts_nested_sensitive_values() -> None:
    payload = {
        "Authorization": "Bearer sk-test-token",
        "database_url": "postgresql+psycopg://dba:plain-password@db.example.com:5432/changeops",
        "messages": [
            {
                "content": (
                    "执行脚本：CONNECT TO PROD USER dba USING password=secret123; "
                    "token: abc.def.ghi"
                )
            }
        ],
        "nested": {
            "api_key": "qwen-secret-key",
            "safe": "保留普通审计字段",
        },
    }

    sanitized = sanitize_audit_payload(payload)

    serialized = json.dumps(sanitized, ensure_ascii=False)
    assert "sk-test-token" not in serialized
    assert "plain-password" not in serialized
    assert "secret123" not in serialized
    assert "abc.def.ghi" not in serialized
    assert "qwen-secret-key" not in serialized
    assert "Bearer ***" in serialized
    assert "postgresql+psycopg://dba:***@db.example.com:5432/changeops" in serialized
    assert "api_key" in sanitized["nested"]
    assert sanitized["nested"]["api_key"] == "***"
    assert sanitized["nested"]["safe"] == "保留普通审计字段"


def test_llm_client_uses_fixture_when_api_key_is_missing() -> None:
    case = make_case()
    case.source_sql = "CONNECT TO PROD USER dba USING password=secret123;"

    result = LLMClient(settings=make_settings(api_key="")).analyze_change(case)

    assert result.status == "fallback"
    assert result.provider == "fixture"
    assert result.model == "offline-demo"
    assert result.latency_ms == 0
    assert result.request_payload["reason"] == "LLM_API_KEY is not configured"
    assert "secret123" not in result.request_payload["prompt"]
    assert "password=***" in result.request_payload["prompt"]
    assert result.data["summary"]
    assert set(result.data["artifacts"]) == set(ARTIFACT_TITLES)


def test_llm_client_parses_openai_compatible_success_response() -> None:
    case = make_case()
    content = {
        "summary": "真实模型摘要",
        "artifacts": {
            "risk_assessment": "真实模型风险",
            "runbook": "真实模型 Runbook",
        },
    }
    response = FakeResponse(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(content, ensure_ascii=False),
                    }
                }
            ]
        }
    )

    def factory(timeout: float) -> FakeHTTPClient:
        assert timeout == 2
        return FakeHTTPClient(response=response)

    result = LLMClient(
        settings=make_settings(api_key="test-key"),
        http_client_factory=factory,
        timeout=2,
    ).analyze_change(case)

    assert result.status == "success"
    assert result.provider == "openai-compatible"
    assert result.model == "qwen-plus"
    assert result.data["summary"] == "真实模型摘要"
    assert result.data["artifacts"]["risk_assessment"] == "真实模型风险"
    assert result.data["artifacts"]["runbook"] == "真实模型 Runbook"
    assert result.data["artifacts"]["rollback_plan"]
    assert FakeHTTPClient.last_request is not None
    assert FakeHTTPClient.last_request["url"] == "https://llm.example.test/v1/chat/completions"
    assert FakeHTTPClient.last_request["headers"]["Authorization"] == "Bearer test-key"
    assert FakeHTTPClient.last_request["json"]["response_format"] == {"type": "json_object"}


def test_llm_client_falls_back_when_provider_times_out() -> None:
    case = make_case()

    def factory(timeout: float) -> FakeHTTPClient:
        assert timeout == 1
        return FakeHTTPClient(error=httpx.TimeoutException("mock timeout"))

    result = LLMClient(
        settings=make_settings(api_key="test-key"),
        http_client_factory=factory,
        timeout=1,
    ).analyze_change(case)

    assert result.status == "fallback"
    assert result.provider == "openai-compatible"
    assert result.model == "qwen-plus"
    assert "mock timeout" in (result.error_message or "")
    assert result.data["summary"]
    assert set(result.data["artifacts"]) == set(ARTIFACT_TITLES)


def test_fixture_analysis_uses_db2_scenario_specific_templates() -> None:
    expected_markers = {
        "db2-index-online": ["EXPLAIN", "DROP INDEX", "SYSCAT.INDEXES"],
        "db2-add-column": ["package rebind", "CHANNEL_CD", "SYSIBM.SYSCOLUMNS"],
        "db2-data-fix": ["备份表", "影响行数", "BAK_CUSTOMER_FLAG_20260602"],
        "db2-reorg": ["SNAPUTIL_PROGRESS", "临时表空间", "06:00"],
        "db2-lock-incident": ["应急指挥", "MON_CURRENT_UOW", "未经批准没有执行 kill session"],
    }

    for fixture in DEMO_CASES:
        case = Case(**{key: value for key, value in fixture.items() if hasattr(Case, key)})
        result = fixture_analysis(case)
        artifact_text = "\n".join(result["artifacts"].values())

        assert set(result["artifacts"]) == set(ARTIFACT_TITLES)
        for marker in expected_markers[fixture["slug"]]:
            assert marker in artifact_text


def test_create_analyze_approve_and_export_workflow() -> None:
    reset_db()
    client = TestClient(app)

    create_response = client.post(
        "/api/cases",
        json={
            "title": "DB2 index change",
            "db_type": "DB2 LUW",
            "target_system": "Settlement",
            "change_type": "Online index creation",
            "priority": "P2",
            "environment": "生产",
            "owner": "结算 DBA",
            "approver": "变更经理",
            "planned_window": "2026-06-03 23:00-00:30",
            "business_context": "Slow monthly report",
            "source_sql": "CREATE INDEX IX_TEST ON APP.T(ID);",
            "schema_notes": "Large table",
            "constraints": "Short maintenance window",
        },
    )
    assert create_response.status_code == 200
    case_id = create_response.json()["id"]

    analyze_response = client.post(f"/api/cases/{case_id}/analyze")
    assert analyze_response.status_code == 200
    payload = analyze_response.json()
    run_id = payload["run_id"]
    assert payload["status"] == "completed"
    assert payload["provider"] == "fixture"
    assert payload["artifact_count"] == len(ARTIFACT_TITLES)
    assert payload["delivery"]["label"] == "0/6 已确认"
    assert payload["delivery"]["pending"] == len(ARTIFACT_TITLES)

    runs_response = client.get(f"/api/cases/{case_id}/runs")
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert len(runs_payload["runs"]) == 1
    assert runs_payload["runs"][0]["delivery"]["percent"] == 0

    db = SessionLocal()
    artifact = db.query(Artifact).filter(Artifact.run_id == run_id).first()
    assert artifact is not None
    artifact_id = artifact.id
    db.close()

    edited_content = "人工编辑后的风险结论：执行前必须补充锁等待截图。"
    edit_response = client.post(f"/api/artifacts/{artifact_id}", json={"content": edited_content})
    assert edit_response.status_code == 200
    assert edit_response.json()["status"] == "draft"

    approve_response = client.post(f"/api/artifacts/{artifact_id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    approved_runs_response = client.get(f"/api/cases/{case_id}/runs")
    assert approved_runs_response.status_code == 200
    approved_delivery = approved_runs_response.json()["runs"][0]["delivery"]
    assert approved_delivery["label"] == "1/6 已确认"
    assert approved_delivery["state_label"] == "还有 5 项待确认"

    db = SessionLocal()
    revisions = (
        db.query(ArtifactRevision)
        .filter(ArtifactRevision.artifact_id == artifact_id)
        .order_by(ArtifactRevision.version.asc())
        .all()
    )
    assert [revision.event for revision in revisions] == ["generated", "edited", "approved"]
    assert revisions[1].content == edited_content
    assert revisions[2].status == "approved"
    db.close()

    revisions_response = client.get(f"/api/artifacts/{artifact_id}/revisions")
    assert revisions_response.status_code == 200
    revisions_payload = revisions_response.json()
    assert revisions_payload["title"]
    assert [revision["version"] for revision in revisions_payload["revisions"]] == [3, 2, 1]
    assert revisions_payload["revisions"][0]["event_label"] == "人工确认"
    assert revisions_payload["revisions"][0]["status_label"] == "已确认"
    assert revisions_payload["revisions"][0]["content"] == edited_content

    diff_response = client.get(f"/api/artifacts/{artifact_id}/diff")
    assert diff_response.status_code == 200
    diff_payload = diff_response.json()["diff"]
    assert diff_payload["available"] is True
    assert diff_payload["from_version"] == 1
    assert diff_payload["to_version"] == 2
    assert diff_payload["from_event_label"] == "AI 生成"
    assert diff_payload["to_event_label"] == "人工编辑"
    assert diff_payload["additions"] >= 1
    assert any(line["kind"] == "add" and edited_content in line["text"] for line in diff_payload["lines"])

    run_page = client.get(f"/cases/{case_id}/runs/{run_id}")
    assert run_page.status_code == 200
    assert "版本记录" in run_page.text
    assert "版本快照" in run_page.text
    assert "最近内容变化" in run_page.text
    assert "差异 JSON" in run_page.text
    assert "新增" in run_page.text
    assert "/api/artifacts/" in run_page.text
    assert "AI 生成" in run_page.text
    assert "人工编辑" in run_page.text
    assert "人工确认" in run_page.text
    assert edited_content in run_page.text
    assert "重新生成交付方案" in run_page.text
    assert "交付完成度" in run_page.text
    assert "1/6 已确认" in run_page.text
    assert "还有 5 项待确认" in run_page.text

    case_page = client.get(f"/cases/{case_id}")
    assert case_page.status_code == 200
    assert "重新生成交付方案" in case_page.text
    assert "1/6 已确认" in case_page.text
    assert "生产" in case_page.text
    assert "结算 DBA" in case_page.text
    assert "变更经理" in case_page.text
    assert "2026-06-03 23:00-00:30" in case_page.text

    home_response = client.get("/")
    assert home_response.status_code == 200
    assert "交付就绪度" in home_response.text
    assert "1/1 个案例已有方案" in home_response.text
    assert "1/6 份交付物已确认" in home_response.text
    assert "0/1 个交付包已签收" in home_response.text
    assert "交付签收" in home_response.text
    assert "待签收" in home_response.text

    markdown_response = client.get(f"/cases/{case_id}/export")
    assert markdown_response.status_code == 200
    assert "# DBA ChangeOps AI 变更交付包" in markdown_response.text
    assert "## 文档封面" in markdown_response.text
    assert "文档编号：CHANGEOPS-" in markdown_response.text
    assert "文档用途：变更评审、执行前沟通、交付存档" in markdown_response.text
    assert "环境：生产" in markdown_response.text
    assert "负责人：结算 DBA" in markdown_response.text
    assert "审批人：变更经理" in markdown_response.text
    assert "计划窗口：2026-06-03 23:00-00:30" in markdown_response.text
    assert "## 目录" in markdown_response.text
    assert "## 交付清单" in markdown_response.text
    assert "审计摘要：1 条调用记录" in markdown_response.text
    assert "风险评估" in markdown_response.text
    assert "执行 Runbook" in markdown_response.text
    assert edited_content in markdown_response.text
    assert "## 交付完成度" in markdown_response.text
    assert "完成度：1/6 已确认" in markdown_response.text
    assert "待确认交付物：" in markdown_response.text
    assert "交付状态：已确认" in markdown_response.text
    assert "### 版本记录" in markdown_response.text
    assert "v1：AI 生成" in markdown_response.text
    assert "v2：人工编辑" in markdown_response.text
    assert "v3：人工确认" in markdown_response.text
    assert "最近内容变化：v1 到 v2 的内容变化" in markdown_response.text
    assert "## LLM 调用审计" in markdown_response.text
    assert "离线兜底" in markdown_response.text
    assert "兜底成功" in markdown_response.text

    pdf_response = client.get(f"/cases/{case_id}/export.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF-1.4")
    assert pdf_contains(pdf_response.content, "DBA ChangeOps AI 变更交付包")
    assert pdf_contains(pdf_response.content, "文档封面")
    assert pdf_contains(pdf_response.content, "文档编号：CHANGEOPS-")
    assert pdf_contains(pdf_response.content, "环境：生产")
    assert pdf_contains(pdf_response.content, "负责人：结算 DBA")
    assert pdf_contains(pdf_response.content, "审批人：变更经理")
    assert pdf_contains(pdf_response.content, "计划窗口：2026-06-03 23:00-00:30")
    assert pdf_contains(pdf_response.content, "目录")
    assert pdf_contains(pdf_response.content, "二、AI 交付概览")
    assert pdf_contains(pdf_response.content, "交付完成度：1/6 已确认")
    assert pdf_contains(pdf_response.content, "交付物数量：6 份")
    assert pdf_contains(pdf_response.content, "三、交付物状态总览")
    assert pdf_contains(pdf_response.content, "五、LLM 调用审计")
    assert pdf_contains(pdf_response.content, "最近内容变化：v1 到 v2 的内容变化")
    assert pdf_contains(pdf_response.content, "第 1 /")

    retry_response = client.post(f"/api/cases/{case_id}/retry")
    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    assert retry_payload["status"] == "completed"
    assert retry_payload["provider"] == "fixture"
    assert retry_payload["artifact_count"] == len(ARTIFACT_TITLES)
    assert retry_payload["delivery"]["label"] == "0/6 已确认"
    assert retry_payload["run_url"] == f"/cases/{case_id}/runs/{retry_payload['run_id']}"
    assert retry_payload["message"] == "已重新生成交付方案"

    rerun_history_response = client.get(f"/api/cases/{case_id}/runs")
    assert rerun_history_response.status_code == 200
    assert [run["id"] for run in rerun_history_response.json()["runs"]] == [
        retry_payload["run_id"],
        run_id,
    ]


def test_create_case_api_rejects_invalid_json_and_field_boundaries() -> None:
    reset_db()
    client = TestClient(app)

    malformed_response = client.post(
        "/api/cases",
        content="{",
        headers={"content-type": "application/json"},
    )
    assert malformed_response.status_code == 400
    assert malformed_response.json()["detail"] == "请求体必须是合法 JSON"

    invalid_response = client.post(
        "/api/cases",
        json={
            "title": "  ",
            "priority": "P9",
            "target_system": "x" * 121,
        },
    )

    assert invalid_response.status_code == 422
    detail = invalid_response.json()["detail"]
    assert "标题不能为空" in detail
    assert "优先级只能是 P1、P2、P3 或 P4" in detail
    assert "目标系统不能超过 120 个字符" in detail


def test_review_inputs_reject_oversized_artifact_and_signoff_fields() -> None:
    reset_db()
    client = TestClient(app)

    create_response = client.post(
        "/api/cases",
        json={
            "title": "DB2 input boundary",
            "db_type": "DB2 LUW",
            "target_system": "Risk",
            "change_type": "Index change",
            "priority": "P2",
        },
    )
    case_id = create_response.json()["id"]
    analyze_response = client.post(f"/api/cases/{case_id}/analyze")
    run_id = analyze_response.json()["run_id"]

    db = SessionLocal()
    artifact = db.query(Artifact).filter(Artifact.run_id == run_id).first()
    assert artifact is not None
    artifact_id = artifact.id
    db.close()

    edit_response = client.post(
        f"/api/artifacts/{artifact_id}",
        json={"content": "x" * 20001},
    )
    assert edit_response.status_code == 422
    assert edit_response.json()["detail"] == "交付物内容不能超过 20000 个字符"

    approve_response = client.post(f"/api/runs/{run_id}/approve-all")
    assert approve_response.status_code == 200
    signoff_response = client.post(
        f"/api/runs/{run_id}/signoff",
        json={"signed_by": "x" * 81, "note": "字段边界测试"},
    )
    assert signoff_response.status_code == 422
    assert signoff_response.json()["detail"] == "签收人不能超过 80 个字符"


def test_run_can_approve_all_artifacts_as_delivery_package() -> None:
    reset_db()
    with TestClient(app) as client:
        create_response = client.post(
            "/api/cases",
            json={
                "title": "DB2 batch approval",
                "db_type": "DB2 LUW",
                "target_system": "Billing",
                "change_type": "Schema change",
                "priority": "P1",
                "business_context": "Release window",
                "source_sql": "ALTER TABLE APP.T ADD COLUMN C VARCHAR(20);",
                "schema_notes": "Synthetic table",
                "constraints": "Need rollback plan",
            },
        )
        case_id = create_response.json()["id"]

        analyze_response = client.post(f"/api/cases/{case_id}/analyze")
        run_id = analyze_response.json()["run_id"]

        run_page = client.get(f"/cases/{case_id}/runs/{run_id}")
        assert run_page.status_code == 200
        assert "确认全部交付物" in run_page.text
        assert "交付签收" in run_page.text
        assert "待签收" in run_page.text
        assert "全部交付物确认后可由审批人签收。" in run_page.text
        assert "0/6 已确认" in run_page.text

        blocked_signoff_response = client.post(
            f"/api/runs/{run_id}/signoff",
            json={"signed_by": "变更经理", "note": "尚未全部确认"},
        )
        assert blocked_signoff_response.status_code == 409
        assert "全部确认" in blocked_signoff_response.json()["detail"]

        approve_all_response = client.post(f"/api/runs/{run_id}/approve-all")
        assert approve_all_response.status_code == 200
        approve_payload = approve_all_response.json()
        assert approve_payload["message"] == "交付包已确认"
        assert approve_payload["delivery"]["label"] == "6/6 已确认"
        assert approve_payload["delivery"]["is_complete"] is True
        assert approve_payload["delivery"]["state_label"] == "交付包已确认，可导出"
        assert approve_payload["signoff"]["label"] == "待签收"

        signoff_response = client.post(
            f"/api/runs/{run_id}/signoff",
            json={"signed_by": "变更经理", "note": "交付包已完成复核。"},
        )
        assert signoff_response.status_code == 200
        signoff_payload = signoff_response.json()
        assert signoff_payload["message"] == "交付包已签收"
        assert signoff_payload["signoff"]["label"] == "已签收"
        assert signoff_payload["signoff"]["signed_by"] == "变更经理"
        assert signoff_payload["signoff"]["signoff_note"] == "交付包已完成复核。"

        runs_response = client.get(f"/api/cases/{case_id}/runs")
        assert runs_response.status_code == 200
        assert runs_response.json()["runs"][0]["signoff"]["label"] == "已签收"

        approved_page = client.get(f"/cases/{case_id}/runs/{run_id}")
        assert approved_page.status_code == 200
        assert "6/6 已确认" in approved_page.text
        assert "交付包已确认，可导出" in approved_page.text
        assert "交付签收" in approved_page.text
        assert "已签收" in approved_page.text
        assert "变更经理" in approved_page.text
        assert "交付包已完成复核。" in approved_page.text
        assert "确认全部交付物" not in approved_page.text

        markdown_response = client.get(f"/cases/{case_id}/export")
        assert markdown_response.status_code == 200
        assert "签收状态：已签收" in markdown_response.text
        assert "签收人：变更经理" in markdown_response.text
        assert "签收说明：交付包已完成复核。" in markdown_response.text

        pdf_response = client.get(f"/cases/{case_id}/export.pdf")
        assert pdf_response.status_code == 200
        assert pdf_contains(pdf_response.content, "签收状态：已签收")
        assert pdf_contains(pdf_response.content, "签收人：变更经理")

        home_response = client.get("/")
        assert home_response.status_code == 200
        assert "1/1 个交付包已签收" in home_response.text
        assert "交付签收" in home_response.text
        assert "已签收" in home_response.text

        ops_response = client.get("/ops")
        assert ops_response.status_code == 200
        assert "1/1 个交付包已签收" in ops_response.text
        assert "交付签收" in ops_response.text

        status_response = client.get("/api/system/status")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["summary"]["signed_runs"] == 1
        assert status_payload["summary"]["signed_label"] == "1/1 个交付包已签收"
        assert {"name": "交付签收", "state": "ok", "label": "1/1 个交付包已签收"} in status_payload[
            "checks"
        ]

    db = SessionLocal()
    approved_revisions = (
        db.query(ArtifactRevision)
        .filter(
            ArtifactRevision.run_id == run_id,
            ArtifactRevision.event == "approved",
        )
        .count()
    )
    approved_artifacts = (
        db.query(Artifact)
        .filter(Artifact.run_id == run_id, Artifact.status == "approved")
        .count()
    )
    db.close()
    assert approved_revisions == len(ARTIFACT_TITLES)
    assert approved_artifacts == len(ARTIFACT_TITLES)


def test_run_signoff_resets_when_artifact_is_edited() -> None:
    reset_db()
    with TestClient(app) as client:
        create_response = client.post(
            "/api/cases",
            json={
                "title": "DB2 signed package edit",
                "db_type": "DB2 LUW",
                "target_system": "Ledger",
                "change_type": "Index change",
                "priority": "P2",
                "business_context": "Need controlled signoff reset",
                "source_sql": "CREATE INDEX IX_LEDGER ON APP.T(ID);",
                "schema_notes": "Synthetic table",
                "constraints": "Short review window",
            },
        )
        case_id = create_response.json()["id"]

        analyze_response = client.post(f"/api/cases/{case_id}/analyze")
        run_id = analyze_response.json()["run_id"]
        approve_all_response = client.post(f"/api/runs/{run_id}/approve-all")
        assert approve_all_response.status_code == 200
        signoff_response = client.post(
            f"/api/runs/{run_id}/signoff",
            json={"signed_by": "DBA 负责人", "note": "已签收"},
        )
        assert signoff_response.status_code == 200
        assert signoff_response.json()["signoff"]["label"] == "已签收"

        db = SessionLocal()
        artifact = db.query(Artifact).filter(Artifact.run_id == run_id).first()
        assert artifact is not None
        artifact_id = artifact.id
        db.close()

        edit_response = client.post(
            f"/api/artifacts/{artifact_id}",
            json={"content": "签收后补充的人工修订，需重新确认。"},
        )
        assert edit_response.status_code == 200
        assert edit_response.json()["status"] == "draft"

        runs_response = client.get(f"/api/cases/{case_id}/runs")
        assert runs_response.status_code == 200
        run_payload = runs_response.json()["runs"][0]
        assert run_payload["delivery"]["is_complete"] is False
        assert run_payload["signoff"]["label"] == "待签收"
        assert run_payload["signoff"]["signed_by"] == ""

        run_page = client.get(f"/cases/{case_id}/runs/{run_id}")
        assert run_page.status_code == 200
        assert "待签收" in run_page.text
        assert "全部交付物确认后可由审批人签收。" in run_page.text


def test_home_page_renders_seeded_demo_cases() -> None:
    reset_db()
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "DBA ChangeOps" in response.text
    assert "包含 5 个内置 DBA 场景，也可加入自定义变更案例" in response.text
    assert "DB2 客户订单慢查询索引变更" in response.text
    assert "AI 变更交付控制台" in response.text
    assert "交付就绪度" in response.text
    assert "0/5 个案例已有方案" in response.text
    assert "暂无交付物" in response.text
    assert "暂无签收记录" in response.text


def test_demo_mode_starts_recommended_case() -> None:
    reset_db()
    with TestClient(app) as client:
        response = client.get("/demo")
        assert response.status_code == 200
        assert "交付演示台" in response.text
        assert "一键生成交付包" in response.text
        assert "一键完整闭环" in response.text
        assert "DB2 客户订单慢查询索引变更" in response.text
        assert "0/5 个案例已有方案" in response.text

        start_response = client.post("/demo/start", follow_redirects=False)
        assert start_response.status_code == 303
        run_url = start_response.headers["location"]
        assert run_url.startswith("/cases/")
        assert "/runs/" in run_url

        run_page = client.get(run_url)
        assert run_page.status_code == 200
        assert "AI 变更交付包" in run_page.text
        assert "交付完成度" in run_page.text
        assert "0/6 已确认" in run_page.text

        demo_after = client.get("/demo")
        assert demo_after.status_code == 200
        assert "1/5 个案例已有方案" in demo_after.text
        assert "0/6 已确认" in demo_after.text
        assert "查看最新交付包" in demo_after.text


def test_demo_complete_creates_signed_delivery_package() -> None:
    reset_db()
    with TestClient(app) as client:
        response = client.get("/demo")
        assert response.status_code == 200
        assert "一键完整闭环" in response.text

        complete_response = client.post("/demo/complete", follow_redirects=False)
        assert complete_response.status_code == 303
        run_url = complete_response.headers["location"]
        assert run_url.startswith("/cases/")
        assert "/runs/" in run_url

        run_page = client.get(run_url)
        assert run_page.status_code == 200
        assert "6/6 已确认" in run_page.text
        assert "交付签收" in run_page.text
        assert "已签收" in run_page.text
        assert "演示交付包已完成复核" in run_page.text
        assert "确认全部交付物" not in run_page.text

        demo_after = client.get("/demo")
        assert demo_after.status_code == 200
        assert "1/5 个案例已有方案" in demo_after.text
        assert "6/6 已确认" in demo_after.text
        assert "1/1 个交付包已签收" in demo_after.text
        assert "已签收" in demo_after.text

        case_id = run_url.split("/")[2]
        markdown_response = client.get(f"/cases/{case_id}/export")
        assert markdown_response.status_code == 200
        assert "签收状态：已签收" in markdown_response.text
        assert "签收说明：演示交付包已完成复核，允许用于变更评审讲解。" in markdown_response.text


def test_operations_status_page_and_api() -> None:
    reset_db()
    with TestClient(app) as client:
        page = client.get("/ops")
        assert page.status_code == 200
        assert "运行状态" in page.text
        assert "交付核验" in page.text
        assert "可交付试运行" in page.text
        assert "离线兜底" in page.text
        assert "查看 JSON" in page.text

        payload_response = client.get("/api/system/status")
        assert payload_response.status_code == 200
        payload = payload_response.json()
        assert payload["service"] == "dba-changeops-ai-workbench"
        assert payload["database_ok"] is True
        assert payload["llm_mode_label"] == "离线兜底"
        assert payload["summary"]["total_cases"] == 5
        assert payload["summary"]["latest_run"] is None
        assert payload["summary"]["signed_runs"] == 0
        assert payload["summary"]["signed_label"] == "暂无签收记录"
        assert [check["name"] for check in payload["checks"]] == [
            "数据库连接",
            "合成案例",
            "交付方案",
            "交付签收",
            "模型模式",
        ]
        signoff_check = next(check for check in payload["checks"] if check["name"] == "交付签收")
        assert signoff_check["state"] == "warning"
        assert signoff_check["label"] == "暂无签收记录"


def test_health_check_verifies_database() -> None:
    reset_db()
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "service": "dba-changeops-ai-workbench",
    }
