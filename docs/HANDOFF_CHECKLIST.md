# 最终交付验收清单

## 当前交付状态

DBA ChangeOps AI 工作台已经具备本地完整演示闭环：创建案例、生成交付包、人工编辑、版本记录、确认、签收、审计、Markdown/PDF 导出和运行状态核验都可以在中文界面中完成。

公开交付项状态：

- 线上部署地址：已完成，`https://dba-changeops-ai-workbench.onrender.com`。
- 备用演示视频：暂缓；建议后续录制 3-5 分钟版本，上传到无需登录即可访问的地址，避免面试现场网络或平台异常影响展示。

## 面试演示入口

- 本地首页：`http://127.0.0.1:8000/`
- 线上首页：`https://dba-changeops-ai-workbench.onrender.com/`
- 线上交付演示台：`https://dba-changeops-ai-workbench.onrender.com/demo`
- 线上运行状态页：`https://dba-changeops-ai-workbench.onrender.com/ops`
- 交付演示台：`http://127.0.0.1:8000/demo`
- 运行状态页：`http://127.0.0.1:8000/ops`
- 健康检查：`http://127.0.0.1:8000/healthz`
- 状态 API：`http://127.0.0.1:8000/api/system/status`
- 安全边界：`SECURITY.md`
- 一页式作品简介：`docs/PORTFOLIO_BRIEF.md`
- 需求覆盖审计：`docs/COMPLETION_AUDIT.md`
- API 契约说明：`docs/API.md`
- 架构决策记录：`docs/DECISIONS.md`
- 面试答辩材料：`docs/INTERVIEW_QA.md`
- 样例 Markdown：`artifacts/samples/changeops-demo-delivery.md`
- 样例 PDF：`artifacts/samples/changeops-demo-delivery.pdf`
- CI 验收：`.github/workflows/ci.yml`
- Render 配置：`render.yaml`
- Railway 配置：`railway.json`
- Fly.io 配置：`fly.toml`
- 线上发布检查表：`docs/RELEASE_CHECKLIST.md`
- 公开投递操作单：`docs/PUBLIC_DELIVERY.md`
- 备用演示视频录制指南：`docs/VIDEO_RECORDING_GUIDE.md`

## 演示前检查

1. 启动服务：

```powershell
uvicorn app.main:app --reload
```

面试现场本地备用演示推荐使用：

```powershell
$env:DATABASE_URL = "sqlite:///:memory:"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

它会以 `sqlite:///:memory:` 启动，避免本机 SQLite 文件权限或路径问题影响演示。

2. 跑单元与集成测试：

```powershell
py -B -m pytest -q -p no:cacheprovider
```

3. 跑离线 DB2 场景评测：

```powershell
py -B -m app.evaluation
```

4. 跑端到端冒烟：

```powershell
.\scripts\smoke_check.ps1 -BaseUrl http://127.0.0.1:8000 -CompleteDemo
```

5. 或者直接运行最终验收脚本：

```powershell
.\scripts\final_acceptance.ps1 -BaseUrl http://127.0.0.1:8000
```

该脚本会覆盖自动化测试、离线 DB2 场景评测、Alembic 迁移链、端到端冒烟、中文界面、部署配置和交付打包检查。

6. 推送到 GitHub 后检查 CI 是否通过；CI 会启动服务、跑最终验收，并刷新样例 Markdown/PDF。

7. 打开 `/demo`，确认推荐案例、中文界面、一键完整闭环和 Markdown/PDF 导出可用。

## 能力覆盖

| 交付要求 | 当前证据 |
| --- | --- |
| 创建变更案例 | `/cases/new`、`POST /api/cases` |
| 外部工单导入 | `POST /api/integrations/work-orders/import`、`app/integrations.py` |
| 工单回写 payload | `GET /api/integrations/work-orders/runs/{run_id}/writeback-payload` |
| ITSM Webhook 回写 | `POST /api/integrations/work-orders/runs/{run_id}/writeback`、`ITSM_WEBHOOK_URL` |
| 工单回写日志 | `GET /api/integrations/work-orders/runs/{run_id}/writebacks`、`work_order_writeback_logs` |
| 失败回写重试 | `POST /api/integrations/work-orders/writebacks/{log_id}/retry` |
| 案例列表和详情 | `/`、`/cases/{id}`、`GET /api/cases`、`GET /api/cases/{id}` |
| 中文本地界面 | Jinja2 模板、`app/static/styles.css` 和本地增强脚本 |
| AI 分析工作流 | `POST /api/cases/{id}/analyze`、`analysis_runs` |
| 国内模型适配 | `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` |
| 无 Key 兜底 | `app/demo_data.py` 场景化 DB2 兜底输出 |
| 离线场景评测 | `app/evaluation.py`、`scripts/evaluate_demo_fixtures.ps1` |
| Alembic 迁移链 | `alembic/versions/`、`scripts/final_acceptance.ps1` |
| 风险、Runbook、回滚、检查、验收、沟通摘要 | 6 类 `artifacts` |
| 人工编辑与确认 | `POST /api/artifacts/{id}`、`POST /api/artifacts/{id}/approve` |
| 版本记录和差异 | `artifact_revisions`、`GET /api/artifacts/{id}/revisions`、`GET /api/artifacts/{id}/diff` |
| 整包确认和签收 | `POST /api/runs/{id}/approve-all`、`POST /api/runs/{id}/signoff` |
| AI 调用审计 | `llm_call_logs` 和结果页右侧审计面板 |
| LLM 审计脱敏 | `app/llm.py` 在 LLM payload 落库前遮蔽常见密码、Token、API Key、Authorization/Cookie/session 字段和连接串口令 |
| 工单回写审计脱敏 | `app/integrations.py` 保持真实 Webhook 发送，同时在日志/API 中遮蔽 URL 查询密钥、Basic Auth 密码、Authorization/Cookie/session 字段和外部响应体敏感字段 |
| Markdown/PDF 导出 | `/cases/{id}/export`、`/cases/{id}/export.pdf` |
| 部署健康检查 | `/healthz`、`/ops`、`/api/system/status` |
| 演示稳定性 | `/demo`、`/demo/complete`、`scripts/smoke_check.ps1` |
| 最终验收入口 | `scripts/final_acceptance.ps1` |
| CI 自动验收 | `.github/workflows/ci.yml` |
| 发布前清理 | `scripts/clean_release_artifacts.ps1` |
| 发布就绪审计 | `scripts/release_readiness.ps1` |
| 部署配置审计 | `scripts/deploy_config_audit.ps1` |
| 面试交付打包 | `scripts/package_release.ps1` |
| README 发布链接回填 | `scripts/update_release_links.ps1` |
| 公开交付总审计 | `scripts/public_delivery_audit.ps1` |
| 当前交付状态汇总 | `scripts/delivery_status.ps1` |
| 项目边界与 Agent 协作规则 | `AGENTS.md` |
| 需求覆盖审计 | `docs/COMPLETION_AUDIT.md` |
| 样例交付包 | `scripts/generate_demo_exports.ps1`、`artifacts/samples/` |

## 面试讲解顺序

1. 首页说明产品定位：不是聊天机器人，而是 DBA 变更交付系统。
2. 进入 `/demo`，用推荐 DB2 索引变更案例一键生成交付包。
3. 展示 6 类交付物、LLM 审计和离线兜底状态。
4. 修改一份交付物，展示版本记录和人工复核边界。
5. 执行整包确认和签收，说明交付完成度。
6. 导出 PDF/Markdown，说明最终材料可以进入审批、评审或归档。
7. 打开 `/ops`，说明部署后如何做健康检查和试运行核验。
8. 如遇现场网络或平台异常，播放按 `docs/VIDEO_RECORDING_GUIDE.md` 准备的备用演示视频；投递前用 `scripts/public_delivery_audit.ps1` 确认视频链接可访问。

## 公开投递执行顺序

1. 推送代码到 GitHub。
2. 任选 Render、Railway 或 Fly.io 部署 Web 服务。
3. 配置托管 PostgreSQL，并把连接串写入 `DATABASE_URL`。
4. 先用离线兜底模式上线，避免真实模型额度或网络影响作品可用性。
5. 用线上地址运行：

```powershell
.\scripts\verify_online_release.ps1 -BaseUrl https://your-app.example.com -CompleteDemo
```

6. 按 `docs/VIDEO_RECORDING_GUIDE.md` 录制 3-5 分钟演示视频，上传为无需登录即可访问的链接。
7. 回填 README：

```powershell
.\scripts\update_release_links.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com
```

8. 跑最终公开交付状态：

```powershell
.\scripts\delivery_status.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com -CompleteDemo -Strict
```

如果按当前策略暂缓视频，先运行：

```powershell
.\scripts\delivery_status.ps1 -CompleteDemo -SkipRuntime
.\scripts\delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo -SkipRuntime
```

README 顶部已有真实在线演示地址时，第一条命令会自动使用该地址；第二条命令用于显式指定候选部署地址。

输出 `summary.demo_ready: true` 时，说明代码、样例材料和线上 Demo 已可面试展示；输出 `ready: false` 和 `delivery_mode: "demo-only"` 是因为严格公开交付仍缺备用视频。`summary.remaining_external_inputs` 会列出后续还需要补齐的外部输入。

## 交付口径

本地代码、线上 Demo 和演示闭环已经达到可面试展示状态。面向严格公开投递时，还需要补齐可访问的备用演示视频，并运行带 `VideoUrl` 的公开交付审计。
