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
from app.integrations import WorkOrderWritebackError, dispatch_work_order_writeback, sanitize_webhook_url
from app.evaluation import SCENARIO_MARKERS, evaluate_demo_fixtures
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


class FakeWebhookResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 202) -> None:
        self.payload = payload or {"accepted": True}
        self.status_code = status_code
        self.text = json.dumps(self.payload, ensure_ascii=False)

    def json(self) -> dict:
        return self.payload


class FakeWebhookClient:
    last_request: dict | None = None

    def __init__(self, response: FakeWebhookResponse) -> None:
        self.response = response

    def __enter__(self) -> "FakeWebhookClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def post(self, url: str, headers: dict, json: dict) -> FakeWebhookResponse:
        FakeWebhookClient.last_request = {"url": url, "headers": headers, "json": json}
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
        "Basic-Auth": "Basic dXNlcjpwYXNz",
        "Cookie": "session=browser-cookie",
        "database_url": "postgresql+psycopg://dba:plain-password@db.example.com:5432/changeops",
        "messages": [
            {
                "content": (
                    "执行脚本：CONNECT TO PROD USER dba USING password=secret123; "
                    "token: abc.def.ghi Authorization: Basic dXNlcjpwYXNz Bearer sk-inline-token"
                )
            }
        ],
        "nested": {
            "api_key": "qwen-secret-key",
            "session_id": "session-secret",
            "safe": "保留普通审计字段",
        },
    }

    sanitized = sanitize_audit_payload(payload)

    serialized = json.dumps(sanitized, ensure_ascii=False)
    assert "sk-test-token" not in serialized
    assert "plain-password" not in serialized
    assert "browser-cookie" not in serialized
    assert "secret123" not in serialized
    assert "abc.def.ghi" not in serialized
    assert "dXNlcjpwYXNz" not in serialized
    assert "sk-inline-token" not in serialized
    assert "qwen-secret-key" not in serialized
    assert "session-secret" not in serialized
    assert "Bearer ***" in serialized
    assert "Basic ***" in serialized
    assert "postgresql+psycopg://dba:***@db.example.com:5432/changeops" in serialized
    assert sanitized["Authorization"] == "***"
    assert sanitized["Basic-Auth"] == "***"
    assert sanitized["Cookie"] == "***"
    assert "api_key" in sanitized["nested"]
    assert sanitized["nested"]["api_key"] == "***"
    assert sanitized["nested"]["session_id"] == "***"
    assert sanitized["nested"]["safe"] == "保留普通审计字段"


def test_sanitize_webhook_url_redacts_query_secrets_and_basic_auth() -> None:
    sanitized = sanitize_webhook_url(
        "https://hook-user:hook-password@itsm.example.test/webhook/changeops"
        "?token=secret-token&safe=visible&signature=abc123"
        "#/callback?access_token=fragment-secret&safe=visible"
    )

    assert sanitized == (
        "https://hook-user:***@itsm.example.test/webhook/changeops"
        "?token=%2A%2A%2A&safe=visible&signature=%2A%2A%2A"
        "#/callback?access_token=%2A%2A%2A&safe=visible"
    )
    assert "hook-password" not in sanitized
    assert "secret-token" not in sanitized
    assert "abc123" not in sanitized
    assert "fragment-secret" not in sanitized


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


def test_llm_client_redacts_sensitive_provider_error_message() -> None:
    case = make_case()
    error = httpx.ConnectError(
        "provider failed for https://llm.example.test/v1/chat/completions"
        "?api_key=provider-secret with Bearer sk-provider-token and password=plain-secret"
    )

    def factory(timeout: float) -> FakeHTTPClient:
        return FakeHTTPClient(error=error)

    result = LLMClient(
        settings=make_settings(api_key="test-key"),
        http_client_factory=factory,
    ).analyze_change(case)

    assert result.status == "fallback"
    assert result.error_message is not None
    assert "provider-secret" not in result.error_message
    assert "sk-provider-token" not in result.error_message
    assert "plain-secret" not in result.error_message
    assert "api_key=***" in result.error_message
    assert "Bearer ***" in result.error_message
    assert "password=***" in result.error_message


def test_fixture_analysis_uses_db2_scenario_specific_templates() -> None:
    for fixture in DEMO_CASES:
        case = Case(**{key: value for key, value in fixture.items() if hasattr(Case, key)})
        result = fixture_analysis(case)
        artifact_text = "\n".join(result["artifacts"].values())

        assert set(result["artifacts"]) == set(ARTIFACT_TITLES)
        for marker in SCENARIO_MARKERS[fixture["slug"]]:
            assert marker in artifact_text


def test_offline_fixture_evaluation_reports_all_db2_scenarios_as_passing() -> None:
    result = evaluate_demo_fixtures()

    assert result["suite"] == "offline-db2-fixture-baseline"
    assert result["total_cases"] == len(DEMO_CASES)
    assert result["passed_cases"] == len(DEMO_CASES)
    assert result["failed_cases"] == []
    assert result["pass_rate"] == 1.0
    assert result["artifact_types"] == list(ARTIFACT_TITLES)
    assert set(SCENARIO_MARKERS) == {fixture["slug"] for fixture in DEMO_CASES}
    assert all(case_result["passed"] for case_result in result["cases"])


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

    run_detail_response = client.get(f"/api/runs/{run_id}")
    assert run_detail_response.status_code == 200
    run_detail_payload = run_detail_response.json()
    assert run_detail_payload["id"] == run_id
    assert run_detail_payload["case"]["id"] == case_id
    assert run_detail_payload["case_inputs"]["source_sql"] == "CREATE INDEX IX_TEST ON APP.T(ID);"
    assert run_detail_payload["delivery"]["label"] == "1/6 已确认"
    assert run_detail_payload["signoff"]["label"] == "待签收"
    assert run_detail_payload["export_urls"] == {
        "markdown": f"/cases/{case_id}/runs/{run_id}/export",
        "pdf": f"/cases/{case_id}/runs/{run_id}/export.pdf",
    }
    assert len(run_detail_payload["artifacts"]) == len(ARTIFACT_TITLES)
    detail_artifact = next(
        artifact for artifact in run_detail_payload["artifacts"] if artifact["id"] == artifact_id
    )
    assert detail_artifact["content"] == edited_content
    assert detail_artifact["status_label"] == "已确认"
    assert detail_artifact["diff"]["available"] is True
    assert detail_artifact["revisions_url"] == f"/api/artifacts/{artifact_id}/revisions"
    assert [revision["event"] for revision in detail_artifact["revisions"]] == [
        "approved",
        "edited",
        "generated",
    ]
    assert len(run_detail_payload["llm_logs"]) == 1
    assert run_detail_payload["llm_logs"][0]["status_label"] == "兜底成功"
    assert run_detail_payload["llm_logs"][0]["request_payload"]["reason"] == (
        "LLM_API_KEY is not configured"
    )

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
    assert f"/cases/{case_id}/runs/{run_id}/export" in run_page.text
    assert f"/cases/{case_id}/runs/{run_id}/export.pdf" in run_page.text
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

    old_run_markdown_response = client.get(f"/cases/{case_id}/runs/{run_id}/export")
    assert old_run_markdown_response.status_code == 200
    assert f"文档编号：CHANGEOPS-{case_id:04d}-RUN-{run_id:04d}" in old_run_markdown_response.text
    assert edited_content in old_run_markdown_response.text

    latest_case_markdown_response = client.get(f"/cases/{case_id}/export")
    assert latest_case_markdown_response.status_code == 200
    assert (
        f"文档编号：CHANGEOPS-{case_id:04d}-RUN-{retry_payload['run_id']:04d}"
        in latest_case_markdown_response.text
    )

    old_run_pdf_response = client.get(f"/cases/{case_id}/runs/{run_id}/export.pdf")
    assert old_run_pdf_response.status_code == 200
    assert old_run_pdf_response.content.startswith(b"%PDF-1.4")
    assert pdf_contains(old_run_pdf_response.content, f"CHANGEOPS-{case_id:04d}-RUN-{run_id:04d}")

    mismatched_run_export_response = client.get(f"/cases/{case_id + 1}/runs/{run_id}/export")
    assert mismatched_run_export_response.status_code == 404
    assert mismatched_run_export_response.json()["detail"] == "分析记录不存在"

    missing_run_response = client.get("/api/runs/999999")
    assert missing_run_response.status_code == 404
    assert missing_run_response.json()["detail"] == "分析记录不存在"


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


def test_work_order_import_maps_external_payload_and_can_analyze() -> None:
    reset_db()
    client = TestClient(app)

    import_response = client.post(
        "/api/integrations/work-orders/import",
        json={
            "ticket_id": "CHG-20260613-001",
            "ticket_url": "https://itsm.example.test/changes/CHG-20260613-001",
            "summary": "DB2 月结批处理 SQL 回放验证",
            "database_type": "DB2 LUW",
            "system": "月结批处理平台",
            "category": "SQL 回放验证",
            "priority": "P1",
            "env": "预生产",
            "requester": "批处理 DBA",
            "approval_owner": "变更经理",
            "window": "2026-06-13 22:00-23:00",
            "description": "月结前需要回放核心 SQL，确认访问计划和耗时变化。",
            "operation_commands": [
                "db2batch -d COREDB -f month_end.sql -o r 5 p 3 -r replay_before.out",
                "RUNSTATS ON TABLE BATCH.MONTH_END WITH DISTRIBUTION AND DETAILED INDEXES ALL;",
            ],
            "affected_objects": "BATCH.MONTH_END、BATCH.MONTH_END_ITEM",
            "impact_scope": "覆盖月结批处理关键查询，不直接修改生产数据。",
            "risk_constraints": "只能在预生产执行，输出需要归档到变更单。",
            "rollback_requirement": "如访问计划退化，回退 RUNSTATS 并保留优化前输出。",
            "labels": ["DB2", "preprod", "replay"],
            "metadata": {
                "requested_by": "ops-bot",
                "source": "itsm",
            },
            "run_analysis": True,
        },
    )

    assert import_response.status_code == 200
    payload = import_response.json()
    assert payload["message"] == "外部工单已导入并生成交付方案"
    assert payload["source"]["external_id"] == "CHG-20260613-001"
    assert payload["source"]["labels"] == ["DB2", "preprod", "replay"]
    assert payload["case"]["title"] == "DB2 月结批处理 SQL 回放验证"
    assert payload["case"]["latest_run"]["id"] == payload["run"]["id"]
    assert payload["run"]["status"] == "completed"
    assert payload["run"]["delivery"]["label"] == "0/6 已确认"
    assert payload["analyze_url"] == f"/api/cases/{payload['case']['id']}/analyze"

    detail_response = client.get(f"/api/cases/{payload['case']['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert "外部工单：CHG-20260613-001" in detail["business_context"]
    assert "工单链接：https://itsm.example.test/changes/CHG-20260613-001" in detail["business_context"]
    assert "工单标签：DB2, preprod, replay" in detail["business_context"]
    assert "- requested_by: ops-bot" in detail["business_context"]
    assert "db2batch -d COREDB" in detail["source_sql"]
    assert "RUNSTATS ON TABLE BATCH.MONTH_END" in detail["source_sql"]
    assert "BATCH.MONTH_END" in detail["schema_notes"]
    assert "不直接修改生产数据" in detail["schema_notes"]
    assert "只能在预生产执行" in detail["constraints"]
    assert "如访问计划退化" in detail["constraints"]

    run_detail_response = client.get(f"/api/runs/{payload['run']['id']}")
    assert run_detail_response.status_code == 200
    artifact_text = "\n".join(artifact["content"] for artifact in run_detail_response.json()["artifacts"])
    assert "db2batch" in artifact_text
    assert "访问计划" in artifact_text


def test_work_order_import_redacts_sensitive_external_url() -> None:
    reset_db()
    client = TestClient(app)

    raw_url = (
        "https://ticket-user:ticket-password@itsm.example.test/changes/CHG-20260613-012"
        "?token=secret-token&safe=visible&api_key=secret-key"
        "#/detail?access_token=fragment-secret&safe=visible"
    )
    sanitized_url = (
        "https://ticket-user:***@itsm.example.test/changes/CHG-20260613-012"
        "?token=%2A%2A%2A&safe=visible&api_key=%2A%2A%2A"
        "#/detail?access_token=%2A%2A%2A&safe=visible"
    )

    import_response = client.post(
        "/api/integrations/work-orders/import",
        json={
            "external_id": "CHG-20260613-012",
            "external_url": raw_url,
            "title": "DB2 外部链接脱敏验证",
            "database_type": "DB2 LUW",
            "target_system": "核心账务",
            "change_type": "审计边界验证",
            "run_analysis": True,
        },
    )

    assert import_response.status_code == 200
    import_payload = import_response.json()
    serialized_import = json.dumps(import_payload, ensure_ascii=False)
    assert import_payload["source"]["external_url"] == sanitized_url
    assert "ticket-password" not in serialized_import
    assert "secret-token" not in serialized_import
    assert "secret-key" not in serialized_import
    assert "fragment-secret" not in serialized_import

    case_response = client.get(f"/api/cases/{import_payload['case']['id']}")
    assert case_response.status_code == 200
    case_payload = case_response.json()
    assert f"工单链接：{sanitized_url}" in case_payload["business_context"]
    assert raw_url not in json.dumps(case_payload, ensure_ascii=False)

    writeback_response = client.get(
        f"/api/integrations/work-orders/runs/{import_payload['run']['id']}/writeback-payload"
    )
    assert writeback_response.status_code == 200
    writeback_payload = writeback_response.json()
    serialized_writeback = json.dumps(writeback_payload, ensure_ascii=False)
    assert writeback_payload["source"]["external_url"] == sanitized_url
    assert "ticket-password" not in serialized_writeback
    assert "secret-token" not in serialized_writeback
    assert "secret-key" not in serialized_writeback
    assert "fragment-secret" not in serialized_writeback


def test_work_order_import_rejects_missing_external_id() -> None:
    reset_db()
    client = TestClient(app)

    response = client.post(
        "/api/integrations/work-orders/import",
        json={"summary": "缺少外部工单号的变更"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "外部工单号不能为空"


def test_work_order_writeback_payload_tracks_delivery_and_signoff_state() -> None:
    reset_db()
    client = TestClient(app)

    import_response = client.post(
        "/api/integrations/work-orders/import",
        json={
            "external_id": "CHG-20260613-009",
            "external_url": "https://itsm.example.test/changes/CHG-20260613-009",
            "title": "DB2 分区归档维护",
            "database_type": "DB2 LUW",
            "target_system": "交易流水平台",
            "change_type": "分区维护",
            "labels": ["DB2", "archive"],
            "run_analysis": True,
        },
    )
    assert import_response.status_code == 200
    run_id = import_response.json()["run"]["id"]

    preview_response = client.get(
        f"/api/integrations/work-orders/runs/{run_id}/writeback-payload"
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["action"] == "work_order_delivery_writeback"
    assert preview["source"]["external_id"] == "CHG-20260613-009"
    assert preview["source"]["external_url"] == "https://itsm.example.test/changes/CHG-20260613-009"
    assert preview["source"]["labels"] == ["DB2", "archive"]
    assert preview["target_status"] == "delivery_generated"
    assert preview["delivery"]["label"] == "0/6 已确认"
    assert preview["signoff"]["label"] == "待签收"
    assert preview["exports"]["markdown"] == f"http://testserver/cases/1/runs/{run_id}/export"
    assert preview["exports"]["pdf"] == f"http://testserver/cases/1/runs/{run_id}/export.pdf"
    assert "DBA ChangeOps 已生成交付包" in preview["comment_markdown"]
    assert "待确认项" in preview["comment_markdown"]
    assert len(preview["artifacts"]) == 6

    approve_response = client.post(f"/api/runs/{run_id}/approve-all")
    assert approve_response.status_code == 200
    signoff_response = client.post(
        f"/api/runs/{run_id}/signoff",
        json={"signed_by": "变更经理", "note": "已回写工单。"},
    )
    assert signoff_response.status_code == 200

    signed_response = client.get(
        f"/api/integrations/work-orders/runs/{run_id}/writeback-payload"
    )
    assert signed_response.status_code == 200
    signed = signed_response.json()
    assert signed["target_status"] == "signed"
    assert signed["delivery"]["label"] == "6/6 已确认"
    assert signed["signoff"]["label"] == "已签收"
    assert signed["signoff"]["signed_by"] == "变更经理"
    assert "签收人：变更经理" in signed["comment_markdown"]


def test_work_order_writeback_payload_requires_imported_work_order_source() -> None:
    reset_db()
    client = TestClient(app)

    create_response = client.post(
        "/api/cases",
        json={
            "title": "普通手工案例",
            "db_type": "DB2 LUW",
            "target_system": "核心系统",
            "change_type": "索引变更",
            "priority": "P2",
        },
    )
    assert create_response.status_code == 200
    case_id = create_response.json()["id"]
    analyze_response = client.post(f"/api/cases/{case_id}/analyze")
    assert analyze_response.status_code == 200
    run_id = analyze_response.json()["run_id"]

    response = client.get(f"/api/integrations/work-orders/runs/{run_id}/writeback-payload")

    assert response.status_code == 422
    assert response.json()["detail"] == "当前分析运行没有关联外部工单"


def test_dispatch_work_order_writeback_sends_configured_webhook_request() -> None:
    payload = {
        "action": "work_order_delivery_writeback",
        "source": {"external_id": "CHG-20260614-001"},
        "target_status": "signed",
    }
    settings = SimpleNamespace(
        itsm_webhook_url="https://itsm.example.test/webhook/changeops",
        itsm_webhook_token="secret-token",
    )

    def factory(timeout: float) -> FakeWebhookClient:
        assert timeout == 3
        return FakeWebhookClient(FakeWebhookResponse({"received": True}, status_code=202))

    result = dispatch_work_order_writeback(
        payload,
        settings,
        http_client_factory=factory,
        timeout=3,
    )

    assert result == {
        "configured": True,
        "url": "https://itsm.example.test/webhook/changeops",
        "status_code": 202,
        "accepted": True,
        "response": {"received": True},
    }
    assert FakeWebhookClient.last_request is not None
    assert FakeWebhookClient.last_request["url"] == "https://itsm.example.test/webhook/changeops"
    assert FakeWebhookClient.last_request["headers"]["Authorization"] == "Bearer secret-token"
    assert FakeWebhookClient.last_request["headers"]["Content-Type"] == "application/json"
    assert FakeWebhookClient.last_request["json"] == payload


def test_dispatch_work_order_writeback_redacts_audit_url_and_response_body() -> None:
    payload = {
        "action": "work_order_delivery_writeback",
        "source": {"external_id": "CHG-20260614-011"},
    }
    raw_webhook_url = (
        "https://hook-user:hook-password@itsm.example.test/webhook/changeops"
        "?token=secret-token&safe=visible"
    )
    settings = SimpleNamespace(
        itsm_webhook_url=raw_webhook_url,
        itsm_webhook_token="secret-token",
    )

    def factory(timeout: float) -> FakeWebhookClient:
        return FakeWebhookClient(
            FakeWebhookResponse(
                {
                    "received": True,
                    "token": "echoed-token",
                    "message": "accepted password=plain-secret",
                },
                status_code=202,
            )
        )

    result = dispatch_work_order_writeback(payload, settings, http_client_factory=factory)

    assert FakeWebhookClient.last_request is not None
    assert FakeWebhookClient.last_request["url"] == raw_webhook_url
    serialized_result = json.dumps(result, ensure_ascii=False)
    assert "hook-password" not in serialized_result
    assert "secret-token" not in serialized_result
    assert "echoed-token" not in serialized_result
    assert "plain-secret" not in serialized_result
    assert result["url"] == (
        "https://hook-user:***@itsm.example.test/webhook/changeops"
        "?token=%2A%2A%2A&safe=visible"
    )
    assert result["response"]["token"] == "***"
    assert result["response"]["message"] == "accepted password=***"


def test_dispatch_work_order_writeback_reports_webhook_http_failure() -> None:
    payload = {"action": "work_order_delivery_writeback"}
    settings = SimpleNamespace(
        itsm_webhook_url="https://itsm.example.test/webhook/changeops",
        itsm_webhook_token="",
    )

    def factory(timeout: float) -> FakeWebhookClient:
        return FakeWebhookClient(FakeWebhookResponse({"error": "bad request"}, status_code=400))

    try:
        dispatch_work_order_writeback(payload, settings, http_client_factory=factory)
    except WorkOrderWritebackError as exc:
        assert str(exc) == "ITSM Webhook 回写失败：HTTP 400"
        assert exc.response_payload == {
            "configured": True,
            "url": "https://itsm.example.test/webhook/changeops",
            "status_code": 400,
            "accepted": False,
            "response": {"error": "bad request"},
        }
    else:
        raise AssertionError("Expected WorkOrderWritebackError for non-success webhook response")


def test_dispatch_work_order_writeback_redacts_network_error_message() -> None:
    payload = {"action": "work_order_delivery_writeback"}
    raw_webhook_url = (
        "https://hook-user:hook-password@itsm.example.test/webhook/changeops"
        "?token=secret-token&safe=visible"
    )
    settings = SimpleNamespace(
        itsm_webhook_url=raw_webhook_url,
        itsm_webhook_token="secret-token",
    )
    error = httpx.ConnectError(
        "connect failed for https://hook-user:hook-password@itsm.example.test/webhook/changeops"
        "?token=secret-token&safe=visible with Bearer secret-token"
    )

    def factory(timeout: float) -> FakeHTTPClient:
        return FakeHTTPClient(error=error)

    try:
        dispatch_work_order_writeback(payload, settings, http_client_factory=factory)
    except WorkOrderWritebackError as exc:
        serialized = json.dumps(exc.response_payload, ensure_ascii=False)
        assert "hook-password" not in str(exc)
        assert "secret-token" not in str(exc)
        assert "hook-password" not in serialized
        assert "secret-token" not in serialized
        assert "Bearer ***" in str(exc)
        assert exc.response_payload["url"] == (
            "https://hook-user:***@itsm.example.test/webhook/changeops"
            "?token=%2A%2A%2A&safe=visible"
        )
    else:
        raise AssertionError("Expected WorkOrderWritebackError for webhook network failure")


def test_work_order_writeback_api_dispatches_configured_webhook(monkeypatch) -> None:
    reset_db()
    client = TestClient(app)
    captured: dict[str, object] = {}

    import_response = client.post(
        "/api/integrations/work-orders/import",
        json={
            "external_id": "CHG-20260614-002",
            "title": "DB2 权限收敛变更",
            "database_type": "DB2 LUW",
            "target_system": "报表平台",
            "change_type": "权限调整",
            "run_analysis": True,
        },
    )
    assert import_response.status_code == 200
    run_id = import_response.json()["run"]["id"]

    def fake_dispatch(payload, settings):
        captured["payload"] = payload
        captured["settings"] = settings
        return {
            "configured": True,
            "url": "https://itsm.example.test/webhook/changeops?token=%2A%2A%2A&safe=visible",
            "status_code": 202,
            "accepted": True,
            "response": {"received": True},
        }

    monkeypatch.setattr("app.main.dispatch_work_order_writeback", fake_dispatch)
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: SimpleNamespace(
            itsm_webhook_url=(
                "https://itsm.example.test/webhook/changeops?token=secret-token&safe=visible"
            ),
            itsm_webhook_token="secret-token",
        ),
    )

    response = client.post(f"/api/integrations/work-orders/runs/{run_id}/writeback")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "外部工单回写已发送"
    assert payload["webhook"]["status_code"] == 202
    assert payload["log"]["status"] == "sent"
    assert payload["log"]["status_label"] == "已发送"
    assert payload["log"]["attempt_count"] == 1
    assert payload["log"]["source_external_id"] == "CHG-20260614-002"
    assert payload["log"]["target_status"] == "delivery_generated"
    assert payload["log"]["response_payload"]["status_code"] == 202
    assert payload["log"]["webhook_url"] == (
        "https://itsm.example.test/webhook/changeops?token=%2A%2A%2A&safe=visible"
    )
    assert payload["log"]["response_payload"]["url"] == (
        "https://itsm.example.test/webhook/changeops?token=%2A%2A%2A&safe=visible"
    )
    assert payload["payload"]["source"]["external_id"] == "CHG-20260614-002"
    assert payload["payload"]["exports"]["markdown"] == f"http://testserver/cases/1/runs/{run_id}/export"
    assert captured["payload"] == payload["payload"]
    assert captured["settings"].itsm_webhook_token == "secret-token"

    logs_response = client.get(f"/api/integrations/work-orders/runs/{run_id}/writebacks")
    assert logs_response.status_code == 200
    logs_payload = logs_response.json()
    assert logs_payload["total"] == 1
    assert logs_payload["writebacks"][0]["id"] == payload["log"]["id"]
    assert logs_payload["writebacks"][0]["request_payload"] == payload["payload"]
    assert "secret-token" not in json.dumps(logs_payload["writebacks"][0], ensure_ascii=False)

    run_detail_response = client.get(f"/api/runs/{run_id}")
    assert run_detail_response.status_code == 200
    assert run_detail_response.json()["writeback_logs"][0]["status"] == "sent"

    retry_response = client.post(
        f"/api/integrations/work-orders/writebacks/{payload['log']['id']}/retry"
    )
    assert retry_response.status_code == 409
    assert retry_response.json()["detail"] == "只有失败的工单回写记录可以重试"


def test_work_order_writeback_api_records_failure_and_retries(monkeypatch) -> None:
    reset_db()
    client = TestClient(app)
    dispatch_calls: list[dict] = []

    import_response = client.post(
        "/api/integrations/work-orders/import",
        json={
            "external_id": "CHG-20260614-004",
            "title": "DB2 慢查询索引修复",
            "database_type": "DB2 LUW",
            "target_system": "交易查询平台",
            "change_type": "索引变更",
            "run_analysis": True,
        },
    )
    assert import_response.status_code == 200
    run_id = import_response.json()["run"]["id"]

    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: SimpleNamespace(
            itsm_webhook_url="https://itsm.example.test/webhook/changeops",
            itsm_webhook_token="secret-token",
        ),
    )

    def failing_dispatch(payload, settings):
        dispatch_calls.append(payload)
        raise WorkOrderWritebackError(
            "ITSM Webhook 回写失败：HTTP 503",
            {
                "configured": True,
                "url": "https://itsm.example.test/webhook/changeops",
                "status_code": 503,
                "accepted": False,
                "response": {"error": "maintenance"},
            },
        )

    monkeypatch.setattr("app.main.dispatch_work_order_writeback", failing_dispatch)

    failed_response = client.post(f"/api/integrations/work-orders/runs/{run_id}/writeback")

    assert failed_response.status_code == 502
    failed_detail = failed_response.json()["detail"]
    assert failed_detail["message"] == "ITSM Webhook 回写失败：HTTP 503"
    assert failed_detail["log"]["status"] == "failed"
    assert failed_detail["log"]["attempt_count"] == 1
    assert failed_detail["log"]["error_message"] == "ITSM Webhook 回写失败：HTTP 503"
    assert failed_detail["log"]["response_payload"] == {
        "configured": True,
        "url": "https://itsm.example.test/webhook/changeops",
        "status_code": 503,
        "accepted": False,
        "response": {"error": "maintenance"},
    }
    failed_log_id = failed_detail["log"]["id"]

    logs_response = client.get(f"/api/integrations/work-orders/runs/{run_id}/writebacks")
    assert logs_response.status_code == 200
    assert logs_response.json()["writebacks"][0]["status"] == "failed"
    assert logs_response.json()["writebacks"][0]["response_payload"]["response"] == {
        "error": "maintenance"
    }

    def successful_dispatch(payload, settings):
        dispatch_calls.append(payload)
        return {
            "configured": True,
            "url": "https://itsm.example.test/webhook/changeops",
            "status_code": 202,
            "accepted": True,
            "response": {"received": True},
        }

    monkeypatch.setattr("app.main.dispatch_work_order_writeback", successful_dispatch)

    retry_response = client.post(
        f"/api/integrations/work-orders/writebacks/{failed_log_id}/retry"
    )

    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    assert retry_payload["message"] == "外部工单回写已重试发送"
    assert retry_payload["previous_log"]["id"] == failed_log_id
    assert retry_payload["previous_log"]["status"] == "failed"
    assert retry_payload["log"]["status"] == "sent"
    assert retry_payload["log"]["attempt_count"] == 2
    assert retry_payload["payload"]["source"]["external_id"] == "CHG-20260614-004"
    assert len(dispatch_calls) == 2

    final_logs_response = client.get(f"/api/integrations/work-orders/runs/{run_id}/writebacks")
    assert final_logs_response.status_code == 200
    final_logs = final_logs_response.json()["writebacks"]
    assert [log["status"] for log in final_logs] == ["sent", "failed"]
    assert [log["attempt_count"] for log in final_logs] == [2, 1]


def test_work_order_writeback_api_requires_configured_webhook() -> None:
    reset_db()
    client = TestClient(app)

    import_response = client.post(
        "/api/integrations/work-orders/import",
        json={
            "external_id": "CHG-20260614-003",
            "title": "DB2 备份恢复演练",
            "database_type": "DB2 LUW",
            "target_system": "灾备平台",
            "change_type": "恢复演练",
            "run_analysis": True,
        },
    )
    assert import_response.status_code == 200
    run_id = import_response.json()["run"]["id"]

    response = client.post(f"/api/integrations/work-orders/runs/{run_id}/writeback")

    assert response.status_code == 422
    assert response.json()["detail"] == "ITSM_WEBHOOK_URL 未配置，无法主动回写工单"


def test_cases_api_lists_and_returns_case_detail_with_latest_run() -> None:
    reset_db()
    client = TestClient(app)

    empty_list_response = client.get("/api/cases")
    assert empty_list_response.status_code == 200
    assert empty_list_response.json() == {"total": 0, "cases": []}

    create_response = client.post(
        "/api/cases",
        json={
            "title": "DB2 query API case",
            "db_type": "DB2 LUW",
            "target_system": "客户订单系统",
            "change_type": "索引变更",
            "priority": "P2",
            "environment": "生产",
            "owner": "结算 DBA",
            "approver": "变更经理",
            "planned_window": "2026-06-03 23:00-00:30",
            "business_context": "验证列表和详情 JSON API 可以被外部系统读取。",
            "source_sql": "CREATE INDEX IX_QUERY_API ON APP.ORDERS(ID);",
            "schema_notes": "合成测试表结构。",
            "constraints": "维护窗口较短。",
        },
    )
    assert create_response.status_code == 200
    case_id = create_response.json()["id"]

    list_response = client.get("/api/cases")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert len(list_payload["cases"]) == 1
    first_case = list_payload["cases"][0]
    assert first_case["id"] == case_id
    assert first_case["title"] == "DB2 query API case"
    assert first_case["latest_run"] is None
    assert first_case["run_count"] == 0
    assert first_case["url"] == f"/cases/{first_case['id']}"

    analyze_response = client.post(f"/api/cases/{first_case['id']}/analyze")
    assert analyze_response.status_code == 200
    run_id = analyze_response.json()["run_id"]

    detail_response = client.get(f"/api/cases/{first_case['id']}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["id"] == first_case["id"]
    assert detail_payload["business_context"]
    assert detail_payload["source_sql"]
    assert detail_payload["run_count"] == 1
    assert len(detail_payload["runs"]) == 1
    assert detail_payload["latest_run"]["id"] == run_id
    assert detail_payload["latest_run"]["delivery"]["label"] == "0/6 已确认"
    assert detail_payload["latest_run"]["signoff"]["label"] == "待签收"
    assert detail_payload["latest_run"]["url"] == f"/cases/{first_case['id']}/runs/{run_id}"

    missing_response = client.get("/api/cases/999999")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "案例不存在"


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
        assert [action["title"] for action in status_payload["next_actions"]] == ["按需接入真实模型"]

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
    assert f"包含 {len(DEMO_CASES)} 个内置 DBA 场景，也可加入自定义变更案例" in response.text
    assert "DB2 客户订单慢查询索引变更" in response.text
    assert "DB2 HADR 受控切换演练" in response.text
    assert "DB2 表空间容量扩容" in response.text
    assert "DB2 报表账号最小权限调整" in response.text
    assert "DB2 备份恢复演练" in response.text
    assert "DB2 SQL 回放验证" in response.text
    assert "DB2 历史分区归档维护" in response.text
    assert "AI 变更交付控制台" in response.text
    assert "交付就绪度" in response.text
    assert f"0/{len(DEMO_CASES)} 个案例已有方案" in response.text
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
        assert f"0/{len(DEMO_CASES)} 个案例已有方案" in response.text

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
        assert f"1/{len(DEMO_CASES)} 个案例已有方案" in demo_after.text
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
        assert f"1/{len(DEMO_CASES)} 个案例已有方案" in demo_after.text
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
        assert "下一步动作" in page.text
        assert "生成首份交付方案" in page.text
        assert "完成一份签收闭环" in page.text

        payload_response = client.get("/api/system/status")
        assert payload_response.status_code == 200
        payload = payload_response.json()
        assert payload["service"] == "dba-changeops-ai-workbench"
        assert payload["database_ok"] is True
        assert payload["llm_mode_label"] == "离线兜底"
        assert payload["summary"]["total_cases"] == len(DEMO_CASES)
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
        assert [action["title"] for action in payload["next_actions"]] == [
            "生成首份交付方案",
            "完成一份签收闭环",
            "按需接入真实模型",
        ]
        assert payload["next_actions"][0]["href"] == "/demo"
        assert payload["next_actions"][0]["cta"] == "打开演示台"


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
