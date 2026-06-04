from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.demo_data import ARTIFACT_TITLES, fixture_analysis
from app.models import Case


SENSITIVE_TEXT_PATTERNS = [
    (
        re.compile(
            r"(?i)\b(password|passwd|pwd|api[_-]?key|token|secret)\b\s*[:=]\s*([^\s,;]+)"
        ),
        r"\1=***",
    ),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer ***"),
    (re.compile(r"(?i)(://[^:/@\s]+:)([^@\s/]+)(@)"), r"\1***\3"),
]


@dataclass
class LLMResult:
    provider: str
    model: str
    status: str
    latency_ms: int
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    data: dict[str, Any]
    error_message: str | None = None


class LLMClient:
    def __init__(
        self,
        settings: Any | None = None,
        http_client_factory: Callable[..., httpx.Client] | None = None,
        timeout: float = 30,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client_factory = http_client_factory or httpx.Client
        self.timeout = timeout

    def analyze_change(self, case: Case) -> LLMResult:
        prompt = build_prompt(case)
        request_payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一名资深数据库运维变更经理，熟悉 DB2 运维、风险控制、"
                        "Runbook、回滚和审计要求。只返回严格 JSON，不要输出额外解释。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        if not self.settings.llm_api_key:
            data = fixture_analysis(case)
            return LLMResult(
                provider="fixture",
                model="offline-demo",
                status="fallback",
                latency_ms=0,
                request_payload=sanitize_audit_payload(
                    {"reason": "LLM_API_KEY is not configured", "prompt": prompt}
                ),
                response_payload=sanitize_audit_payload(data),
                data=data,
            )

        start = time.perf_counter()
        try:
            with self.http_client_factory(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                    json=request_payload,
                )
                response.raise_for_status()
                payload = response.json()
            latency_ms = int((time.perf_counter() - start) * 1000)
            content = payload["choices"][0]["message"]["content"]
            data = normalize_response(json.loads(content), case)
            return LLMResult(
                provider="openai-compatible",
                model=self.settings.llm_model,
                status="success",
                latency_ms=latency_ms,
                request_payload=sanitize_audit_payload(request_payload),
                response_payload=sanitize_audit_payload(payload),
                data=data,
            )
        except Exception as exc:  # Keep live demos resilient when providers fail.
            latency_ms = int((time.perf_counter() - start) * 1000)
            data = fixture_analysis(case)
            return LLMResult(
                provider="openai-compatible",
                model=self.settings.llm_model,
                status="fallback",
                latency_ms=latency_ms,
                request_payload=sanitize_audit_payload(request_payload),
                response_payload=sanitize_audit_payload(data),
                data=data,
                error_message=str(exc),
            )


def sanitize_audit_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sanitized[key] = "***"
            else:
                sanitized[key] = sanitize_audit_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_audit_payload(item) for item in value]
    if isinstance(value, str):
        text = value
        for pattern, replacement in SENSITIVE_TEXT_PATTERNS:
            text = pattern.sub(replacement, text)
        return text
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(
        marker in normalized
        for marker in ("api_key", "apikey", "token", "secret", "password", "passwd", "pwd")
    )


def build_prompt(case: Case) -> str:
    artifact_keys = ", ".join(ARTIFACT_TITLES)
    return f"""
请为下面的数据库运维变更生成一套中文交付方案。

必须返回以下 JSON 结构：
{{
  "summary": "简短管理摘要",
  "artifacts": {{
    "risk_assessment": "中文 Markdown 风险评估",
    "runbook": "中文 Markdown 执行 Runbook",
    "rollback_plan": "中文 Markdown 回滚方案",
    "precheck_sql": "SQL 或带中文注释的检查脚本",
    "acceptance_checklist": "中文 Markdown 验收清单",
    "communication_summary": "面向干系人的中文沟通摘要"
  }}
}}

必须包含这些交付物键：{artifact_keys}

案例：
- 标题：{case.title}
- 数据库：{case.db_type}
- 目标系统：{case.target_system}
- 变更类型：{case.change_type}
- 优先级：{case.priority}
- 业务背景：{case.business_context}
- SQL 或操作命令：
{case.source_sql}
- 表结构说明：{case.schema_notes}
- 约束条件：{case.constraints}
""".strip()


def normalize_response(data: dict[str, Any], case: Case) -> dict[str, Any]:
    fallback = fixture_analysis(case)
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
    normalized = {
        "summary": str(data.get("summary") or fallback["summary"]),
        "artifacts": {},
    }
    for key in ARTIFACT_TITLES:
        value = artifacts.get(key) or fallback["artifacts"][key]
        normalized["artifacts"][key] = str(value)
    return normalized
