# 需求覆盖审计

本文件把最初的 DBA ChangeOps AI 工作台计划逐项映射到当前仓库证据，便于面试前自查，也便于面试官快速判断项目完成度。

## 审计结论

当前仓库已经具备本地完整演示闭环：中文 Web 工作台、案例创建、外部工单导入、工单回写 payload、ITSM Webhook 主动回写、回写日志、失败重试、Webhook 审计脱敏、AI 分析、离线兜底、AI 调用审计、人工编辑、版本记录、差异查看、交付确认、整包签收、Markdown/PDF 导出、样例交付包、截图、部署配置、测试、离线 DB2 场景评测、冒烟验收、发布就绪审计和中文界面审计。

仍需外部补齐的项：

- 线上部署 URL：已完成，`https://dba-changeops-ai-workbench.onrender.com`。
- 备用演示视频：暂缓；后续补齐无需登录的视频地址。

## 产品能力覆盖

| 计划能力 | 当前证据 | 验收方式 |
| --- | --- | --- |
| 创建变更案例 | `POST /api/cases`、`POST /cases`、`app/templates/new_case.html` | `tests/test_workflow.py` |
| 外部工单导入 | `POST /api/integrations/work-orders/import`、`app/integrations.py` | 工单导入测试 |
| 工单回写 payload | `GET /api/integrations/work-orders/runs/{run_id}/writeback-payload`、`build_work_order_writeback_payload` | 工单回写测试 |
| ITSM Webhook 回写 | `POST /api/integrations/work-orders/runs/{run_id}/writeback`、`dispatch_work_order_writeback`、`ITSM_WEBHOOK_URL` | Webhook 回写测试 |
| 工单回写日志和重试 | `work_order_writeback_logs`、`GET /api/integrations/work-orders/runs/{run_id}/writebacks`、`POST /api/integrations/work-orders/writebacks/{log_id}/retry` | 回写失败与重试测试 |
| Webhook 审计脱敏 | `sanitize_webhook_url`、`sanitize_audit_payload`、`work_order_writeback_logs` | URL 密钥、Basic Auth 密码、Authorization/Cookie/session 字段和外部响应体脱敏测试 |
| 案例列表和详情页 | `/`、`/cases/{id}`、`GET /api/cases`、`GET /api/cases/{id}`、`app/templates/home.html`、`app/templates/case_detail.html` | 工作流测试、首页测试、中文界面审计 |
| AI 分析触发 | `POST /api/cases/{id}/analyze`、`POST /cases/{id}/analyze` | 工作流测试、冒烟脚本 |
| 历史分析记录 | `GET /api/cases/{id}/runs`、`analysis_runs` | 工作流测试 |
| 风险评估 | `risk_assessment` 交付物 | 工作流测试检查 6 类交付物 |
| 执行 Runbook | `runbook` 交付物 | 工作流测试检查 6 类交付物 |
| 回滚方案 | `rollback_plan` 交付物 | 工作流测试检查 6 类交付物 |
| 前置检查 SQL | `precheck_sql` 交付物 | 工作流测试检查 6 类交付物 |
| 验收清单 | `acceptance_checklist` 交付物 | 工作流测试检查 6 类交付物 |
| 变更沟通摘要 | `communication_summary` 交付物 | 工作流测试检查 6 类交付物 |
| AI 调用审计 | `llm_call_logs`、结果页审计面板、导出文档审计段落 | 工作流测试、导出测试 |
| 人工编辑 | `POST /api/artifacts/{id}`、交付物编辑区 | 工作流测试 |
| 单项确认 | `POST /api/artifacts/{id}/approve` | 工作流测试 |
| 整包确认 | `POST /api/runs/{id}/approve-all` | 签收工作流测试 |
| 交付签收 | `POST /api/runs/{id}/signoff`、`analysis_runs.signoff_*` 字段 | 签收测试、导出测试 |
| 版本记录 | `artifact_revisions`、`GET /api/artifacts/{id}/revisions` | 工作流测试 |
| 差异查看 | `GET /api/artifacts/{id}/diff`、结果页差异面板 | 工作流测试 |
| Markdown 导出 | `/cases/{id}/export` | 冒烟脚本、工作流测试 |
| PDF 导出 | `/cases/{id}/export.pdf` | 冒烟脚本、工作流测试 |
| 一键演示闭环 | `/demo/start`、`/demo/complete` | 演示闭环测试 |
| 运行状态页 | `/ops`、`/api/system/status` | 运行状态测试、冒烟脚本 |
| 离线场景评测 | `app/evaluation.py`、`scripts/evaluate_demo_fixtures.ps1` | 评测测试、最终验收脚本 |

## 接口覆盖

| 计划接口 | 当前状态 | 证据 |
| --- | --- | --- |
| `POST /api/cases` | 已实现 | `app/main.py` |
| `GET /api/cases` | 已实现 | `app/main.py` |
| `GET /api/cases/{id}` | 已实现 | `app/main.py` |
| `POST /api/integrations/work-orders/import` | 已实现 | `app/main.py`、`app/integrations.py` |
| `GET /api/integrations/work-orders/runs/{run_id}/writeback-payload` | 已实现 | `app/main.py`、`app/integrations.py` |
| `POST /api/integrations/work-orders/runs/{run_id}/writeback` | 已实现 | `app/main.py`、`app/integrations.py` |
| `GET /api/integrations/work-orders/runs/{run_id}/writebacks` | 已实现 | `app/main.py`、`work_order_writeback_logs` |
| `POST /api/integrations/work-orders/writebacks/{log_id}/retry` | 已实现 | `app/main.py`、`work_order_writeback_logs` |
| `POST /api/cases/{id}/analyze` | 已实现 | `app/main.py` |
| `GET /api/cases/{id}/runs` | 已实现 | `app/main.py` |
| `POST /api/artifacts/{id}/approve` | 已实现 | `app/main.py` |

额外补充接口：

- `GET /api/system/status`：运行状态和演示就绪度。
- `POST /api/cases/{id}/retry`：重新生成交付方案。
- `GET /api/artifacts/{id}/revisions`：交付物版本历史。
- `GET /api/artifacts/{id}/diff`：交付物内容差异。
- `POST /api/runs/{id}/approve-all`：整包确认。
- `POST /api/runs/{id}/signoff`：签收交付包。
- `POST /api/artifacts/{id}`：人工编辑交付物。

## 数据模型覆盖

| 计划表 | 当前状态 | 说明 |
| --- | --- | --- |
| `cases` | 已实现 | 保存变更案例、数据库类型、目标系统、SQL、业务背景、环境、负责人、审批人和计划窗口。 |
| `analysis_runs` | 已实现 | 保存每次 AI 分析、模型状态、摘要、错误信息和签收信息。 |
| `artifacts` | 已实现 | 保存 6 类当前交付物及确认状态。 |
| `llm_call_logs` | 已实现 | 保存模型请求/响应审计、耗时、状态和失败原因。 |
| `work_order_writeback_logs` | 已实现 | 保存工单 Webhook 回写 attempt、请求 payload、脱敏后的响应 payload、状态和失败原因。 |
| `demo_fixtures` | 已实现 | 保存内置合成演示案例载荷。 |

额外补充表：

- `artifact_revisions`：保存交付物 AI 生成、人工编辑、人工确认等版本快照。

## AI 工作流覆盖

| 计划项 | 当前证据 | 验收方式 |
| --- | --- | --- |
| OpenAI-compatible 适配层 | `app/llm.py` | LLM 适配层测试 |
| `LLM_BASE_URL` | `app/config.py`、`.env.example`、README、部署文档 | 文档和测试 |
| `LLM_API_KEY` | `app/config.py`、`.env.example`、README、部署文档 | 兜底测试 |
| `LLM_MODEL` | `app/config.py`、`.env.example`、README、部署文档 | 真实模型 mock 测试 |
| 国内模型优先 | README 和部署文档提供通义千问兼容地址示例 | 文档审计 |
| 无 Key 兜底 | `fixture_analysis`、`LLMClient.analyze_change` | 兜底测试 |
| 调用失败兜底 | `LLMClient.analyze_change` | 超时兜底测试 |
| 结构化输出 | `normalize_response`、`ARTIFACT_TITLES` | 结构化输出测试 |
| LLM 审计脱敏 | `sanitize_audit_payload` | LLM payload、Authorization/Cookie/session 字段和 provider 异常脱敏测试 |
| 工单回写审计脱敏 | `sanitize_webhook_url`、`sanitize_audit_payload` | Webhook URL 查询密钥、Basic Auth 密码、Authorization/Cookie/session 字段和外部响应体脱敏测试 |
| 离线场景评测 | `evaluate_demo_fixtures`、`SCENARIO_MARKERS` | 11 个 DB2 场景结构和关键标记评测 |

## 文档和交付资产

| 资产 | 当前文件 |
| --- | --- |
| README | `README.md` |
| Render 部署配置 | `render.yaml` |
| Railway 部署配置 | `railway.json` |
| Fly.io 部署配置 | `fly.toml` |
| 通用容器配置 | `Dockerfile`、`.dockerignore` |
| 一页式作品简介 | `docs/PORTFOLIO_BRIEF.md` |
| 需求覆盖审计 | `docs/COMPLETION_AUDIT.md` |
| 架构说明 | `docs/ARCHITECTURE.md` |
| 架构决策记录 | `docs/DECISIONS.md` |
| API 契约说明 | `docs/API.md` |
| 部署说明 | `docs/DEPLOYMENT.md` |
| 3-5 分钟演示脚本 | `docs/DEMO_SCRIPT.md` |
| 面试答辩材料 | `docs/INTERVIEW_QA.md` |
| 发布检查表 | `docs/RELEASE_CHECKLIST.md` |
| 公开投递操作单 | `docs/PUBLIC_DELIVERY.md` |
| 备用视频录制指南 | `docs/VIDEO_RECORDING_GUIDE.md` |
| 截图刷新说明 | `docs/SCREENSHOTS.md` |
| 最终交付验收清单 | `docs/HANDOFF_CHECKLIST.md` |
| 样例 Markdown | `artifacts/samples/changeops-demo-delivery.md` |
| 样例 PDF | `artifacts/samples/changeops-demo-delivery.pdf` |
| 产品截图 | `artifacts/screenshots/home.png`、`artifacts/screenshots/demo.png`、`artifacts/screenshots/run-detail.png` |
| 项目边界与 Agent 协作规则 | `AGENTS.md` |
| 安全边界 | `SECURITY.md` |
| 面试交付压缩包脚本 | `scripts/package_release.ps1` |
| README 发布链接回填脚本 | `scripts/update_release_links.ps1` |
| 公开交付总审计脚本 | `scripts/public_delivery_audit.ps1` |
| 当前交付状态汇总脚本 | `scripts/delivery_status.ps1` |
| 交付状态契约测试脚本 | `scripts/test_delivery_status_contract.ps1` |
| 离线 DB2 场景评测脚本 | `scripts/evaluate_demo_fixtures.ps1` |

## 验收命令

完整本地验收：

```powershell
.\scripts\final_acceptance.ps1 -BaseUrl http://127.0.0.1:8000
```

该脚本会串联测试、离线 DB2 场景评测、Alembic 迁移链、端到端冒烟、中文界面审计、部署配置审计和交付打包检查。

发布前文件和运行状态审计：

```powershell
.\scripts\release_readiness.ps1 -BaseUrl http://127.0.0.1:8000
```

该审计同时检查 README 顶部是否回填真实 HTTPS 在线演示地址，并检查本地运行产物是否已清理，避免把 `.env`、数据库、日志、进程 pid 文件或缓存带入公开交付。

线上发布验收：

```powershell
.\scripts\verify_online_release.ps1 -BaseUrl https://your-app.example.com -CompleteDemo
```

README 发布链接回填：

```powershell
.\scripts\update_release_links.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com
```

公开交付总审计：

```powershell
.\scripts\public_delivery_audit.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com -CompleteDemo
```

该脚本不仅检查 README 是否回填链接，也会实际访问线上演示地址和备用视频地址。备用视频如果仍是私有链接、登录后可见链接或已过期分享链接，不算完成公开交付。

视频暂缓时，可以先运行：

```powershell
.\scripts\delivery_status.ps1 -CompleteDemo -SkipRuntime
.\scripts\delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo -SkipRuntime
```

README 顶部已经包含真实在线演示地址时，第一条命令会自动读取该地址；第二条命令用于检查指定的候选部署地址。

其中 `demo_ready: true` 表示本地材料和线上 Demo 已可展示；`ready: false` 表示还缺公开视频链接，不能宣称严格公开交付完成。
输出中的 `summary.remaining_external_inputs` 会列出剩余外部输入；视频暂缓时应只剩 `VideoUrl`。

部署配置一致性审计：

```powershell
.\scripts\deploy_config_audit.ps1
```

交付状态契约测试：

```powershell
.\scripts\test_delivery_status_contract.ps1
```

该脚本不访问外网，用于确认缺少外部 URL 时不会误报 demo-ready，并确认非 localhost 的 `http://` URL 不会绕过 HTTPS 边界。

中文界面交付证据审计：

```powershell
.\scripts\ui_text_audit.ps1
```

样例交付包刷新：

```powershell
.\scripts\generate_demo_exports.ps1 -BaseUrl http://127.0.0.1:8000
```

发布前清理：

```powershell
.\scripts\clean_release_artifacts.ps1 -WhatIf
.\scripts\clean_release_artifacts.ps1
```

生成面试交付压缩包：

```powershell
.\scripts\package_release.ps1
```

## 完成度边界

本地仓库和线上 Demo 已经达到可面试演示和可交付试运行状态。严格意义上的完整公开交付仍需外部动作完成：

1. 录制并上传 3-5 分钟备用演示视频。
2. 将视频链接回填到 README 顶部。
3. 使用 `scripts/delivery_status.ps1 -Strict` 或 `scripts/public_delivery_audit.ps1` 确认线上演示和视频链接都可访问。
