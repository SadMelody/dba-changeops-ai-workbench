# API 契约说明

DBA ChangeOps AI 工作台同时提供中文页面和 JSON API。页面用于演示完整工作流，API 用于说明系统具备清晰的服务边界，后续可以接入工单系统、审批平台或自动化脚本。

默认本地地址：

```text
http://127.0.0.1:8000
```

FastAPI 自动生成的交互式文档也可访问：

```text
/docs
```

## 健康与运行状态

### `GET /healthz`

用于部署平台健康检查。

响应示例：

```json
{
  "status": "ok",
  "database": "ok",
  "service": "dba-changeops-ai-workbench"
}
```

状态码：

- `200`：服务和数据库正常。
- `503`：服务已启动，但数据库连接异常。

### `GET /api/system/status`

用于上线后验收和自动化冒烟检查。

响应字段包含：

- `ready`：是否满足试运行条件。
- `database`：数据库状态和脱敏连接信息。
- `llm`：模型模式，显示真实模型或离线兜底。
- `summary`：案例、分析、交付物、确认和签收统计。
- `checks`：逐项检查结果。
- `next_actions`：基于当前状态生成的下一步动作，包含严重程度、说明和页面入口。

## 案例与分析

### `GET /api/cases`

查询案例列表，供工单系统、自动化脚本或外部展示页同步当前工作台状态。

响应示例：

```json
{
  "total": 11,
  "cases": [
    {
      "id": 1,
      "title": "DB2 客户订单慢查询索引变更",
      "db_type": "DB2 LUW",
      "target_system": "客户订单系统",
      "change_type": "索引变更",
      "priority": "P2",
      "environment": "生产",
      "owner": "结算 DBA",
      "approver": "变更经理",
      "planned_window": "2026-06-03 23:00-00:30",
      "status": "draft",
      "created_at": "2026-06-02 18:00",
      "updated_at": "2026-06-02 18:00",
      "latest_run": null,
      "run_count": 0,
      "url": "/cases/1"
    }
  ]
}
```

### `GET /api/cases/{case_id}`

查询单个案例详情，包含输入材料、最新分析运行和历史运行摘要。

响应字段在列表摘要基础上额外包含：

- `business_context`
- `source_sql`
- `schema_notes`
- `constraints`
- `runs`

状态码：

- `200`：查询成功。
- `404`：案例不存在。

### `POST /api/cases`

创建变更案例。

请求示例：

```json
{
  "title": "DB2 客户订单慢查询索引变更",
  "db_type": "DB2 LUW",
  "target_system": "客户订单系统",
  "change_type": "索引变更",
  "priority": "P2",
  "environment": "生产",
  "owner": "结算 DBA",
  "approver": "变更经理",
  "planned_window": "2026-06-03 23:00-00:30",
  "business_context": "订单查询高峰期 P95 响应时间超过 3 秒。",
  "source_sql": "CREATE INDEX IDX_ORDERS_CUST_DATE ON APP.ORDERS(CUSTOMER_ID, CREATED_AT);",
  "schema_notes": "APP.ORDERS 约 8000 万行。",
  "constraints": "窗口期 90 分钟，不能影响核心下单。"
}
```

响应示例：

```json
{
  "id": 6,
  "title": "DB2 客户订单慢查询索引变更",
  "status": "draft"
}
```

状态码：

- `200`：创建成功。
- `400`：请求体不是合法 JSON。
- `422`：请求体不是 JSON 对象，或字段不满足边界要求。

字段边界：

- `title` 必填，最多 180 个字符。
- `priority` 只能是 `P1`、`P2`、`P3` 或 `P4`。
- `db_type`、`environment` 最多 40 个字符。
- `target_system`、`planned_window` 最多 120 个字符。
- `change_type`、`owner`、`approver` 最多 80 个字符。
- `business_context`、`schema_notes`、`constraints` 最多 4000 个字符。
- `source_sql` 最多 12000 个字符。

### `POST /api/integrations/work-orders/import`

从外部工单系统导入变更需求。这个接口适合 ITSM、Jira、ServiceNow 或自动化脚本把工单字段映射成 ChangeOps 案例；不要求外部系统字段名完全一致，接口会识别常见别名。

请求示例：

```json
{
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
    "RUNSTATS ON TABLE BATCH.MONTH_END WITH DISTRIBUTION AND DETAILED INDEXES ALL;"
  ],
  "affected_objects": "BATCH.MONTH_END、BATCH.MONTH_END_ITEM",
  "risk_constraints": "只能在预生产执行，输出需要归档到变更单。",
  "labels": ["DB2", "preprod", "replay"],
  "metadata": {
    "source": "itsm"
  },
  "run_analysis": true
}
```

响应示例：

```json
{
  "message": "外部工单已导入并生成交付方案",
  "source": {
    "external_id": "CHG-20260613-001",
    "external_url": "https://itsm.example.test/changes/CHG-20260613-001",
    "labels": ["DB2", "preprod", "replay"]
  },
  "case": {
    "id": 12,
    "title": "DB2 月结批处理 SQL 回放验证",
    "latest_run": {
      "id": 31,
      "status": "completed"
    }
  },
  "run": {
    "id": 31,
    "status": "completed",
    "delivery": {
      "label": "0/6 已确认"
    }
  },
  "analyze_url": "/api/cases/12/analyze"
}
```

字段说明：

- `ticket_id`、`external_id` 或 `change_id`：外部工单号，必填。
- `summary` 或 `title`：变更标题，必填。
- `database_type`/`db_type`、`system`/`target_system`、`category`/`change_type` 等字段会映射到内部案例字段。
- `operation_commands` 可传字符串数组；如果已经有完整 SQL，也可以直接传 `source_sql`、`sql` 或 `change_script`。
- `labels` 和 `metadata` 会写入业务背景，方便后续人工复核追溯来源。
- `run_analysis: true` 会在导入后立即生成交付方案；不传则只创建案例。

状态码：

- `200`：导入成功。
- `400`：请求体不是合法 JSON。
- `422`：请求体不是 JSON 对象，缺少外部工单号/标题，或字段不满足内部案例边界。

### `GET /api/integrations/work-orders/runs/{run_id}/writeback-payload`

生成外部工单回写 payload。这个接口不会主动调用真实 ITSM，而是把签收状态、交付完成度、导出链接和工单评论内容组织成稳定 JSON，方便预览、调试或接入 Jira、ServiceNow、企业微信审批和内部工单 API。

响应示例：

```json
{
  "action": "work_order_delivery_writeback",
  "source": {
    "external_id": "CHG-20260613-001",
    "external_url": "https://itsm.example.test/changes/CHG-20260613-001",
    "labels": ["DB2", "preprod", "replay"]
  },
  "target_status": "signed",
  "delivery": {
    "label": "6/6 已确认",
    "percent": 100
  },
  "signoff": {
    "label": "已签收",
    "signed_by": "变更经理"
  },
  "exports": {
    "markdown": "http://127.0.0.1:8000/cases/12/runs/31/export",
    "pdf": "http://127.0.0.1:8000/cases/12/runs/31/export.pdf"
  },
  "comment_markdown": "DBA ChangeOps 已生成交付包..."
}
```

`target_status` 会随交付状态变化：

- `delivery_generated`：已生成交付物，但尚未全部确认。
- `ready_for_signoff`：交付物已全部确认，等待签收。
- `signed`：交付包已签收，可把导出链接和签收信息回写工单。

状态码：

- `200`：回写 payload 生成成功。
- `404`：分析记录不存在。
- `422`：该分析记录不是从外部工单导入，缺少外部工单号。

### `POST /api/integrations/work-orders/runs/{run_id}/writeback`

主动把外部工单回写 payload 发送到配置的 ITSM Webhook。这个接口复用上面的标准 payload，并按环境变量配置追加 Bearer Token，适合先接通真实工单系统的通用 Webhook，再逐步做厂商字段映射。

需要配置：

- `ITSM_WEBHOOK_URL`：Webhook 地址，必填；未配置时接口返回 `422`。
- `ITSM_WEBHOOK_TOKEN`：可选认证 Token；配置后请求头会带 `Authorization: Bearer <token>`。

响应示例：

```json
{
  "message": "外部工单回写已发送",
  "payload": {
    "action": "work_order_delivery_writeback",
    "source": {
      "external_id": "CHG-20260613-001"
    },
    "target_status": "signed"
  },
  "webhook": {
    "configured": true,
    "url": "https://itsm.example.test/webhook/changeops",
    "status_code": 202,
    "accepted": true,
    "response": {
      "received": true
    }
  },
  "log": {
    "id": 8,
    "status": "sent",
    "attempt_count": 1,
    "source_external_id": "CHG-20260613-001",
    "target_status": "signed"
  }
}
```

状态码：

- `200`：Webhook 已返回 2xx/3xx，视为发送成功。
- `404`：分析记录不存在。
- `422`：未配置 `ITSM_WEBHOOK_URL`，或分析记录缺少外部工单号。
- `502`：外部 Webhook 返回 4xx/5xx；失败 attempt 会写入 `work_order_writeback_logs`。

### `GET /api/integrations/work-orders/runs/{run_id}/writebacks`

查看某次分析运行的外部工单回写记录。每次主动发送或失败重试都会生成一条 attempt，便于演示真实系统接入时的追踪能力。

响应示例：

```json
{
  "run_id": 31,
  "total": 2,
  "writebacks": [
    {
      "id": 9,
      "status": "sent",
      "status_label": "已发送",
      "attempt_count": 2,
      "source_external_id": "CHG-20260613-001",
      "target_status": "signed",
      "webhook_url": "https://itsm.example.test/webhook/changeops",
      "error_message": null
    },
    {
      "id": 8,
      "status": "failed",
      "status_label": "失败",
      "attempt_count": 1,
      "source_external_id": "CHG-20260613-001",
      "target_status": "signed",
      "error_message": "ITSM Webhook 回写失败：HTTP 503"
    }
  ]
}
```

状态码：

- `200`：返回该运行的回写记录。
- `404`：分析记录不存在。

### `POST /api/integrations/work-orders/writebacks/{log_id}/retry`

重试一条失败的工单回写记录。重试会基于当前分析运行重新生成 payload，并创建新的 attempt；成功记录不会被允许重试，避免重复写入外部工单。

响应示例：

```json
{
  "message": "外部工单回写已重试发送",
  "previous_log": {
    "id": 8,
    "status": "failed",
    "attempt_count": 1
  },
  "log": {
    "id": 9,
    "status": "sent",
    "attempt_count": 2
  }
}
```

状态码：

- `200`：重试发送成功。
- `404`：回写记录或分析记录不存在。
- `409`：该记录不是失败状态，不能重试。
- `422`：未配置 `ITSM_WEBHOOK_URL`，或分析记录缺少外部工单号。
- `502`：外部 Webhook 再次失败，并写入新的失败 attempt。

### `POST /api/cases/{case_id}/analyze`

触发一次 AI 分析。未配置 `LLM_API_KEY` 或模型调用失败时，系统会自动使用场景化离线兜底，并写入 LLM 调用审计。审计 payload 落库前会遮蔽常见密码、Token、API Key 和连接串口令。

响应示例：

```json
{
  "run_id": 12,
  "case_id": 6,
  "status": "completed",
  "provider": "fallback",
  "model": "offline-demo",
  "artifact_count": 6,
  "run_url": "/cases/6/runs/12",
  "message": "交付方案已生成"
}
```

状态码：

- `200`：分析完成，可能是真实模型结果，也可能是离线兜底结果。
- `404`：案例不存在。

### `POST /api/cases/{case_id}/retry`

重新生成交付方案。它会创建新的 `analysis_run`，不会覆盖历史运行记录。

### `GET /api/cases/{case_id}/runs`

查看案例的历史分析记录。

响应字段包含：

- `id`
- `status`
- `provider`
- `model`
- `completed_at`
- `summary`
- `delivery`
- `signoff`

### `GET /api/runs/{run_id}`

查询单次分析运行的完整交付包 JSON，适合外部系统同步交付物、审计记录或自动化验收。

响应字段在运行摘要基础上额外包含：

- `case`：案例摘要和页面入口。
- `case_inputs`：本次分析使用的业务背景、SQL、表结构和约束。
- `artifacts`：6 类交付物正文、确认状态、版本记录、最近内容差异和版本 API 链接。
- `llm_logs`：模型提供方、模型名、状态、耗时、失败原因，以及已脱敏的请求和响应审计 payload。
- `writeback_logs`：外部工单 Webhook 回写 attempt、状态、目标工单号、目标状态、响应和失败原因。
- `export_urls`：固定到本次运行记录的 Markdown 和 PDF 交付包下载入口。

状态码：

- `200`：查询成功。
- `404`：分析记录不存在。

## 交付物复核

### `POST /api/artifacts/{artifact_id}`

人工编辑交付物内容。保存后交付物状态回到 `draft`，并写入版本记录；如果当前运行记录已签收，会重置为待签收。

请求示例：

```json
{
  "content": "人工复核后的风险评估内容。"
}
```

响应示例：

```json
{
  "id": 21,
  "status": "draft",
  "updated_at": "2026-06-02 18:30"
}
```

状态码：

- `200`：保存成功。
- `404`：交付物不存在。
- `422`：内容为空，或超过 20000 个字符。

### `POST /api/artifacts/{artifact_id}/approve`

确认单份交付物。

响应示例：

```json
{
  "id": 21,
  "status": "approved",
  "approved_at": "2026-06-02 18:35"
}
```

### `POST /api/runs/{run_id}/approve-all`

整包确认，把一次分析运行下的所有交付物确认到可导出状态。

响应字段包含：

- `delivery`：交付完成度，例如 `6/6`。
- `signoff`：签收状态，整包确认后通常仍为待签收。

### `POST /api/runs/{run_id}/signoff`

签收交付包。只有全部交付物确认后才能签收。

请求示例：

```json
{
  "signed_by": "变更经理",
  "note": "交付包已完成复核，允许进入变更评审。"
}
```

状态码：

- `200`：签收成功。
- `404`：分析记录不存在。
- `409`：交付物尚未全部确认，不能签收。
- `422`：签收人超过 80 个字符，或签收说明超过 2000 个字符。

## 版本与差异

### `GET /api/artifacts/{artifact_id}/revisions`

查看交付物版本历史。

版本事件：

- `generated`：AI 生成。
- `edited`：人工编辑。
- `approved`：人工确认。

### `GET /api/artifacts/{artifact_id}/diff`

查看最近一次真实内容变化。用于解释 AI 初稿和人工编辑之间的差异。

响应示例：

```json
{
  "artifact_id": 21,
  "title": "风险评估",
  "diff": {
    "label": "v1 到 v2 的内容变化",
    "added": ["新增的人工风险说明"],
    "removed": ["删除的原始说明"]
  }
}
```

## 导出

### `GET /cases/{case_id}/export`

导出该案例最新一次运行的 Markdown 交付包。适合页面按钮或演示场景快速下载当前最新材料。

响应头：

```text
Content-Type: text/markdown; charset=utf-8
Content-Disposition: attachment; filename="changeops-case-{case_id}.md"
```

### `GET /cases/{case_id}/export.pdf`

导出该案例最新一次运行的 PDF 交付包。

响应头：

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="changeops-case-{case_id}.pdf"
```

### `GET /cases/{case_id}/runs/{run_id}/export`

导出指定分析运行的 Markdown 交付包。这个入口不会随着后续重新生成而变化，适合审计归档和外部系统固定引用。

状态码：

- `200`：导出成功。
- `404`：案例或分析记录不存在，或该分析记录不属于该案例。

### `GET /cases/{case_id}/runs/{run_id}/export.pdf`

导出指定分析运行的 PDF 交付包。语义与 Markdown 固定导出一致。

响应头：

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="changeops-case-{case_id}-run-{run_id}.pdf"
```

## PowerShell 调用示例

```powershell
$base = "http://127.0.0.1:8000"

$case = Invoke-RestMethod -Method Post -Uri "$base/api/cases" -ContentType "application/json" -Body (@{
    title = "DB2 客户订单慢查询索引变更"
    db_type = "DB2 LUW"
    target_system = "客户订单系统"
    change_type = "索引变更"
    priority = "P2"
    environment = "生产"
    owner = "结算 DBA"
    approver = "变更经理"
    planned_window = "2026-06-03 23:00-00:30"
    business_context = "订单查询高峰期 P95 响应时间超过 3 秒。"
    source_sql = "CREATE INDEX IDX_ORDERS_CUST_DATE ON APP.ORDERS(CUSTOMER_ID, CREATED_AT);"
    schema_notes = "APP.ORDERS 约 8000 万行。"
    constraints = "窗口期 90 分钟，不能影响核心下单。"
} | ConvertTo-Json)

$run = Invoke-RestMethod -Method Post -Uri "$base/api/cases/$($case.id)/analyze"
Invoke-RestMethod -Method Post -Uri "$base/api/runs/$($run.run_id)/approve-all"
Invoke-RestMethod -Method Post -Uri "$base/api/runs/$($run.run_id)/signoff" -ContentType "application/json" -Body (@{
    signed_by = "变更经理"
    note = "交付包已完成复核。"
} | ConvertTo-Json)

Invoke-WebRequest -Uri "$base/cases/$($case.id)/export" -OutFile "changeops-case-$($case.id).md"
Invoke-WebRequest -Uri "$base/cases/$($case.id)/export.pdf" -OutFile "changeops-case-$($case.id).pdf"
```
