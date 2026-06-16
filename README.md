# DBA ChangeOps AI 工作台

一个面向数据库运维/DBA 场景的 AI 变更交付系统。它不是通用聊天机器人，而是把一段变更需求、SQL、表结构说明或故障描述，转成一套可以交付和审计的变更材料。

在线演示：https://dba-changeops-ai-workbench.onrender.com

备用材料：

- [Markdown 样例交付包](artifacts/samples/changeops-demo-delivery.md)
- [PDF 样例交付包](artifacts/samples/changeops-demo-delivery.pdf)
- [3-5 分钟演示脚本](docs/DEMO_SCRIPT.md)
- [备用演示视频录制指南](docs/VIDEO_RECORDING_GUIDE.md)
- [公开投递操作单](docs/PUBLIC_DELIVERY.md)

当前版本支持：

- 风险评估
- 执行 Runbook
- 回滚方案
- 前置检查 SQL
- 验收清单
- 变更沟通摘要
- AI 调用审计
- LLM 审计脱敏：落库前遮蔽常见密码、Token、API Key、Authorization/Cookie/session 字段和连接串口令
- 工单回写审计脱敏：Webhook 发送仍使用真实配置，但日志/API 会遮蔽 URL 查询串和 fragment 密钥、Basic Auth 密码、Authorization/Cookie/session 字段和外部响应体中的敏感字段
- 交付封面元数据：环境、负责人、审批人、计划窗口
- 人工编辑、确认、版本快照、版本差异对比和版本 API 查询
- 交付包签收：整包确认后由审批人签收，签收记录进入页面、API 和导出文档
- 分析失败提示和重新生成入口
- 外部工单导入、回写 payload、Webhook API、回写日志和失败重试：把 ITSM/Jira 类工单载荷映射为变更案例，并在签收后生成或主动发送交付状态、导出链接和评论内容
- 首页交付就绪度总览，展示案例、方案、确认进度、签收进度和兜底记录
- `/demo` 交付演示台，提供推荐案例、一键生成、一键完整闭环和导出入口
- `/ops` 运行状态页，集中展示数据库、模型模式、案例、交付和签收统计
- DB2 场景化兜底输出，覆盖索引变更、新增字段、数据修复、REORG/RUNSTATS、锁等待应急、HADR 受控切换、表空间扩容、权限收敛、备份恢复、SQL 回放验证和分区维护
- 交付完成度、待确认项总览和复核进度提示
- 单份确认、整包确认和交付签收，支持把一次分析结果快速收敛为可导出交付包
- 带文档封面、目录、交付清单、状态、版本、页码和 LLM 审计的结构化 Markdown/PDF 导出
- 离线 DB2 场景评测基线：校验 11 个内置场景都产出完整 6 类交付物，并命中关键 DBA 标记
- 无 API Key 的离线兜底

这个项目按真实产品闭环来设计：输入、生成、复核、确认、审计、导出都能落到可交付材料上。它既适合技术展示，也具备继续扩展到内部变更评审工具的基础。

## 产品截图

首页用交付就绪度说明案例、方案、人工确认和签收状态：

![首页交付就绪度](artifacts/screenshots/home.png)

交付演示台提供固定演示路径和一键完整闭环：

![交付演示台](artifacts/screenshots/demo.png)

结果页展示交付物、版本记录、LLM 审计、整包确认和签收状态：

![AI 变更交付包结果页](artifacts/screenshots/run-detail.png)

样例交付包已经放在 README 顶部备用材料区。

## 演示路径

1. 打开首页，先看“交付就绪度”，说明案例数量、已生成方案、确认进度、签收进度和兜底记录。
2. 进入 `/demo` 交付演示台，使用推荐的 DB2 慢查询索引变更案例。
3. 点击“一键生成交付包”；如果现场时间很短，也可以点击“一键完整闭环”直接生成、确认并签收。
4. 查看交付封面元数据，以及风险、Runbook、回滚、前置检查、验收和沟通摘要。
5. 查看右侧 LLM 调用审计，确认离线兜底或真实模型调用状态；需要时可重新生成交付方案。
6. 查看交付完成度，确认哪些交付物还待人工复核。
7. 对任意交付物进行人工编辑，保存后状态回到“草稿”。
8. 点击“确认”或“确认全部交付物”，查看完成度变化、版本记录、最近内容变化和可展开的版本快照。
9. 整包确认后点击“签收交付包”，记录签收人、签收时间和签收说明。
10. 回到 `/demo` 或案例页导出 Markdown/PDF，作为包含封面、目录、完成度、签收状态、版本记录、页码和 LLM 审计的最终变更交付包。
11. 打开 `/ops`，确认数据库、模型模式、案例和交付统计满足试运行条件。

应用即使没有配置模型 Key 也能完整生成交付包。未设置 `LLM_API_KEY` 或模型调用失败时，系统会记录失败原因，并按案例类型使用内置合成 DBA 输出兜底，避免试运行、评审或现场讲解受网络、额度或模型服务影响。当前兜底内容已区分 DB2 索引变更、新增字段、数据修复、REORG/RUNSTATS、锁等待应急、HADR 受控切换、表空间扩容、权限收敛、备份恢复、SQL 回放验证和分区维护等典型场景。

## 技术栈

- 后端：FastAPI
- 页面：Jinja2 服务端渲染 + 原生增强脚本，无前端构建步骤
- 样式：自定义 CSS，中文工作台界面
- 数据访问：SQLAlchemy
- 迁移：Alembic
- 本地数据库：SQLite
- 云数据库：PostgreSQL 兼容 `DATABASE_URL`
- AI 适配：OpenAI-compatible Chat Completions 接口
- 导出：Markdown / PDF
- 测试：pytest + FastAPI TestClient

## 快速启动

```powershell
.\scripts\setup_dev_env.ps1
.\.venv\Scripts\Activate.ps1
copy .env.example .env
uvicorn app.main:app --reload
```

打开：

```text
http://127.0.0.1:8000
```

面试现场建议用内存数据库启动本地备用演示，避免本机 SQLite 文件权限、路径或锁问题影响展示：

```powershell
$env:DATABASE_URL = "sqlite:///:memory:"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

该方式只用于现场演示；正式部署仍建议配置 PostgreSQL。

如果不配置 `.env`，默认会在用户数据目录下创建本地 SQLite 数据库，避免 Windows 非 ASCII 项目路径造成 SQLite 文件锁或路径问题。

## 模型配置

支持通义千问、DeepSeek 等兼容 OpenAI Chat Completions 协议的模型服务。

```text
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your-api-key
LLM_MODEL=qwen-plus
```

只要服务暴露 `/chat/completions` 兼容接口，就可以通过上述变量接入。模型响应需要返回结构化 JSON；如果返回不完整，系统会用内置字段补齐必需交付物。

## 数据库配置

本地开发可以不配置 `DATABASE_URL`，系统会使用 SQLite。

云部署建议使用 Neon、Supabase、Railway、Render PostgreSQL 或其他托管 PostgreSQL：

```text
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
```

当前依赖已经包含 `psycopg[binary]`，部署环境设置好 `DATABASE_URL` 后即可连接 PostgreSQL。

## 部署说明

Render/Railway/Fly.io 的基础配置：

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/healthz`
- Runtime readiness: `/ops` 或 `/api/system/status`
- Container: 仓库提供 `Dockerfile` 和 `.dockerignore`，可用于 Fly.io 或通用容器平台
- Render Blueprint: 仓库提供 `render.yaml`
- Railway: 仓库提供 `railway.json`
- Fly.io: 仓库提供 `fly.toml`
- Environment variables:
  - `DATABASE_URL`
  - `LLM_BASE_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL`

为了方便演示，应用启动时会自动创建数据表并写入合成案例。项目同时保留 Alembic 迁移，后续进入生产化阶段可以切换为显式迁移流程。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

离线场景评测可以单独运行：

```powershell
.\scripts\evaluate_demo_fixtures.ps1 -PythonCommand .\.venv\Scripts\python.exe
```

它会输出 JSON 评测报告，检查 11 个内置 DB2 场景的交付物结构和场景关键标记。

部署或演示前可以运行 smoke check：

```powershell
.\scripts\smoke_check.ps1 -BaseUrl http://127.0.0.1:8000 -CompleteDemo
```

它会检查健康状态、运行状态页、演示台、一键完整闭环，以及 Markdown/PDF 导出。

面试前建议运行最终验收脚本：

```powershell
.\scripts\final_acceptance.ps1 -BaseUrl http://127.0.0.1:8000
```

它会依次执行自动化测试、离线 DB2 场景评测和端到端冒烟验收。
同时会检查中文界面交付证据、部署配置一致性和面试交付包打包能力。

推送到 GitHub 后，`.github/workflows/ci.yml` 会在 Linux runner 上安装依赖、启动本地服务、运行最终验收脚本，并刷新样例 Markdown/PDF 交付包。最终验收会覆盖自动化测试、离线 DB2 场景评测、Alembic 迁移链、端到端冒烟、中文界面、部署配置和打包检查，用于证明项目不是只在本机偶然可跑。

需要刷新样例交付包时：

```powershell
.\scripts\generate_demo_exports.ps1 -BaseUrl http://127.0.0.1:8000
```

打包或公开提交前可以预览并清理本地运行产物：

```powershell
.\scripts\clean_release_artifacts.ps1 -WhatIf
.\scripts\clean_release_artifacts.ps1
```

需要生成一份不包含 `.env`、本地数据库、日志和缓存的面试交付压缩包时：

```powershell
.\scripts\package_release.ps1
```

打包脚本也会排除 `.omx/` 和 `outputs/` 等本地工具或临时输出目录，避免把 Codex/演示生成物混入公开交付包。

发布前可以运行交付就绪审计：

```powershell
.\scripts\release_readiness.ps1 -BaseUrl http://127.0.0.1:8000
```

这个检查会要求 README 顶部已经回填真实 HTTPS 在线演示地址，核心交付文档不再残留示例 DemoUrl，并要求 `.env`、本地数据库、日志、进程 pid 文件和 Python 缓存已经清理，适合作为公开提交或打包前的最后一道门。

线上部署完成后，用真实地址运行发布验收：

```powershell
.\scripts\verify_online_release.ps1 -BaseUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo
```

线上地址和备用视频准备好后，可以自动回填 README 顶部发布区：

```powershell
$VideoUrl = Read-Host "VideoUrl"
.\scripts\update_release_links.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -VideoUrl $VideoUrl
```

公开投递前，用线上地址和视频地址运行最终公开交付审计：

```powershell
$VideoUrl = Read-Host "VideoUrl"
.\scripts\public_delivery_audit.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -VideoUrl $VideoUrl -CompleteDemo
```

该审计会同时访问线上应用和备用视频地址；视频链接如果是私有、过期、需要登录或返回 404，会被视为未完成公开交付。

如果想随时查看“本地已就绪、线上还差什么”，运行交付状态汇总：

```powershell
.\scripts\delivery_status.ps1 -BaseUrl http://127.0.0.1:8000
$VideoUrl = Read-Host "VideoUrl"
.\scripts\delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -VideoUrl $VideoUrl -CompleteDemo -Strict
```

视频暂缓时，可以先用真实 Demo 地址检查代码、样例材料和线上闭环；如果 README 顶部已经回填了在线演示地址，`-SkipRuntime` 会自动读取：

```powershell
.\scripts\delivery_status.ps1 -CompleteDemo -SkipRuntime
.\scripts\delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo -SkipRuntime
```

这时重点看输出里的 `summary`：

- `summary.demo_ready: true` 表示代码、样例材料和线上 Demo 已可面试展示。
- `delivery_mode: "demo-only"` 表示当前是“可演示但非严格公开交付”。
- 总 `ready` 仍会保持 `false`，直到补齐可访问的备用视频并通过严格公开交付审计。

如需在不访问外网的情况下回归交付状态语义，可以运行：

```powershell
.\scripts\test_delivery_status_contract.ps1
.\scripts\test_release_readiness_contract.ps1
```

这些脚本会验证缺少 `DemoUrl`/`VideoUrl` 时不会误报 demo-ready、非 localhost 的 `http://` 地址会被拒绝，并确认发布就绪审计仍保护核心交付文档不回退到模板 URL。

需要单独检查部署配置一致性时：

```powershell
.\scripts\deploy_config_audit.ps1
```

当前测试覆盖：

- 创建案例
- 保存交付封面元数据
- LLM 适配层：无 Key 兜底、兼容接口成功、提供方超时兜底
- 结构化输出解析和缺失交付物字段补齐
- 触发 AI 分析和离线兜底
- 11 类 DB2 演示案例的场景化兜底内容
- 生成 6 类交付物
- 保存人工编辑
- 记录版本历史和版本快照
- 展示和查询最近一次内容变化
- 查询交付物版本 API
- 确认交付物
- 整包确认并记录每份交付物的确认版本
- 交付包签收、签收前置条件和签收后编辑失效
- 统计交付完成度、待确认项和签收进度
- 渲染首页交付就绪度总览
- 通过交付演示台一键生成推荐案例交付包
- 通过交付演示台一键完成生成、整包确认和签收
- 查看运行状态页和系统状态 API
- 查询分析历史
- 导出带文档封面、目录、完成度、签收、版本、审计信息和页码的 Markdown/PDF
- 渲染首页内置合成案例

## 项目结构

```text
app/
  main.py              FastAPI 路由、页面入口和 API
  models.py            SQLAlchemy 数据模型
  services.py          案例、分析、交付物、签收和版本记录业务逻辑
  llm.py               OpenAI-compatible 模型适配和兜底处理
  demo_data.py         合成 DBA 案例和兜底输出
  exporter.py          Markdown/PDF 导出
  templates/           中文页面模板
  static/              样式和前端增强脚本
alembic/               数据库迁移
tests/                 工作流测试
scripts/               冒烟检查、离线评测和最终验收脚本
docs/                  架构说明和演示脚本
artifacts/samples/     可直接展示的样例交付包
```

扩展文档：

- [项目边界与 Agent 协作规则](AGENTS.md)
- [安全边界](SECURITY.md)
- [一页式作品简介](docs/PORTFOLIO_BRIEF.md)
- [需求覆盖审计](docs/COMPLETION_AUDIT.md)
- [架构说明](docs/ARCHITECTURE.md)
- [架构决策记录](docs/DECISIONS.md)
- [API 契约说明](docs/API.md)
- [部署清单](docs/DEPLOYMENT.md)
- [3-5 分钟演示脚本](docs/DEMO_SCRIPT.md)
- [面试答辩材料](docs/INTERVIEW_QA.md)
- [线上发布检查表](docs/RELEASE_CHECKLIST.md)
- [公开投递操作单](docs/PUBLIC_DELIVERY.md)
- [备用演示视频录制指南](docs/VIDEO_RECORDING_GUIDE.md)
- [截图刷新说明](docs/SCREENSHOTS.md)
- [最终交付验收清单](docs/HANDOFF_CHECKLIST.md)

## 产品讲解重点

- 这不是“套壳聊天机器人”，而是受控的 DBA 变更交付工作流。
- 数据模型拆分为案例、分析运行、交付物、交付物版本和 LLM 调用日志，能解释审计追踪。
- LLM 和工单回写审计会在落库前脱敏常见密码、Token、API Key、Authorization/Cookie/session 字段、连接串口令、Webhook URL 查询串/fragment 密钥和外部响应体敏感字段，兼顾可追溯性和公开演示安全边界。
- 版本差异能说明 AI 初稿和 DBA 人工修改之间的具体变化。
- 无 Key 兜底让试运行稳定，场景化 DB2 模板让离线演示仍然有领域可信度，真实模型接入又能展示工程扩展性。
- 交付完成度把 AI 输出转成可复核、可确认、可导出的交付闭环。
- 整包确认让现场试运行可以快速进入“可交付、可导出、可审计”的完成状态。
- 交付签收把整包确认后的责任人、时间和说明沉淀下来，更接近正式变更评审材料。
- Markdown/PDF 导出像正式变更交付包，而不是页面内容复制。
- 交付物对应真实 DBA 工作：风险、执行、回滚、前置检查、验收和沟通。
- 交付封面字段让导出文档具备环境、负责人、审批人和窗口信息，而不是只有 AI 文本。
- 合成数据避免真实公司数据泄露，符合产品试运行和公开讲解的安全边界。
- 中文界面和中文输出适合国内 DBA/运维/AI 应用场景。
- 页面不依赖外部前端 CDN，现场无公网时仍可稳定展示核心流程。
- `/demo` 交付演示台降低现场操作风险，能按固定路径展示完整闭环，也能一键快进到已签收状态。
- `/ops` 运行状态页把部署后的健康检查、模型模式、交付数据和签收统计收敛到一个可核验入口。

## 下一步计划

- 补充产品讲解视频，并用 `scripts/delivery_status.ps1 -VideoUrl $VideoUrl -CompleteDemo -Strict` 做严格公开交付审计。
- 扩充真实评测样本，并逐步接入只读 DB2 检查账号、审批评论同步和具体 ITSM 字段映射。
