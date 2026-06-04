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

## 案例与分析

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
- `422`：标题为空或请求体不完整。

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
- `422`：内容为空。

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

导出 Markdown 交付包。

响应头：

```text
Content-Type: text/markdown; charset=utf-8
Content-Disposition: attachment; filename="changeops-case-{case_id}.md"
```

### `GET /cases/{case_id}/export.pdf`

导出 PDF 交付包。

响应头：

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="changeops-case-{case_id}.pdf"
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
