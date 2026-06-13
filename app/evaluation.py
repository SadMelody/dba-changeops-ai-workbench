from __future__ import annotations

import json
import sys
from typing import Any

from app.demo_data import ARTIFACT_TITLES, DEMO_CASES, fixture_analysis
from app.models import Case


SCENARIO_MARKERS = {
    "db2-index-online": ["EXPLAIN", "DROP INDEX", "SYSCAT.INDEXES"],
    "db2-add-column": ["package rebind", "CHANNEL_CD", "SYSIBM.SYSCOLUMNS"],
    "db2-data-fix": ["备份表", "影响行数", "BAK_CUSTOMER_FLAG_20260602"],
    "db2-reorg": ["SNAPUTIL_PROGRESS", "临时表空间", "06:00"],
    "db2-lock-incident": ["应急指挥", "MON_CURRENT_UOW", "未经批准没有执行 kill session"],
    "db2-hadr-takeover": ["HADR_STATE=PEER", "TAKEOVER HADR", "db2pd -db COREDB -hadr"],
    "db2-tablespace-expand": ["TS_TXN_DATA", "CONTAINER_UTILIZATION", "文件系统空间"],
    "db2-privilege-change": ["SYSCAT.TABAUTH", "BI_REPORT", "INSERT/UPDATE/DELETE 权限已移除"],
    "db2-backup-restore": ["RESTORE DATABASE", "ROLLFORWARD", "COREDB_DR"],
    "db2-sql-replay": ["db2batch", "replay_before.out", "访问计划"],
    "db2-partition-maintenance": ["SYSCAT.DATAPARTITIONS", "DETACH PARTITION", "TXN_EVENT_2025Q4_ARCHIVE"],
}

CASE_FIELDS = {
    "title",
    "db_type",
    "target_system",
    "change_type",
    "priority",
    "environment",
    "owner",
    "approver",
    "planned_window",
    "business_context",
    "source_sql",
    "schema_notes",
    "constraints",
}


def _case_from_fixture(fixture: dict[str, Any]) -> Case:
    return Case(**{key: value for key, value in fixture.items() if key in CASE_FIELDS})


def _evaluate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    case = _case_from_fixture(fixture)
    result = fixture_analysis(case)
    artifacts = result["artifacts"]
    artifact_keys = set(artifacts)
    expected_keys = set(ARTIFACT_TITLES)
    missing_artifacts = sorted(expected_keys - artifact_keys)
    extra_artifacts = sorted(artifact_keys - expected_keys)
    artifact_text = "\n".join(str(content) for content in artifacts.values())
    markers = SCENARIO_MARKERS.get(fixture["slug"], [])
    marker_checks = [
        {
            "marker": marker,
            "ok": marker in artifact_text,
        }
        for marker in markers
    ]
    artifact_shape_ok = not missing_artifacts and not extra_artifacts
    marker_hits = sum(1 for check in marker_checks if check["ok"])
    total_checks = len(marker_checks) + 1
    passed_checks = marker_hits + (1 if artifact_shape_ok else 0)
    passed = passed_checks == total_checks
    return {
        "slug": fixture["slug"],
        "title": fixture["title"],
        "passed": passed,
        "score": round(passed_checks / total_checks, 4) if total_checks else 1.0,
        "checks": {
            "artifact_shape": {
                "ok": artifact_shape_ok,
                "expected_count": len(expected_keys),
                "actual_count": len(artifact_keys),
                "missing": missing_artifacts,
                "extra": extra_artifacts,
            },
            "markers": marker_checks,
        },
    }


def evaluate_demo_fixtures(fixtures: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    fixtures = fixtures or DEMO_CASES
    case_results = [_evaluate_fixture(fixture) for fixture in fixtures]
    passed_cases = sum(1 for case_result in case_results if case_result["passed"])
    total_cases = len(case_results)
    failed_cases = [
        case_result["slug"] for case_result in case_results if not case_result["passed"]
    ]
    return {
        "suite": "offline-db2-fixture-baseline",
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "pass_rate": round(passed_cases / total_cases, 4) if total_cases else 1.0,
        "artifact_types": list(ARTIFACT_TITLES),
        "marker_policy": "每个内置 DB2 场景必须产出完整 6 类交付物，并命中该场景的关键 DBA 标记。",
        "cases": case_results,
    }


def main() -> int:
    result = evaluate_demo_fixtures()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["failed_cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
