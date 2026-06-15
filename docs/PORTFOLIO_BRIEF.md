# DBA ChangeOps AI 工作台作品简介

## 一句话定位

DBA ChangeOps AI 工作台是一款面向数据库运维变更场景的 AI 交付系统：把变更需求、SQL、表结构说明或故障描述，转成风险评估、执行 runbook、回滚方案、前置检查 SQL、验收清单、沟通摘要和审计记录。

它不是通用聊天机器人，而是一个可演示、可审计、可导出的数据库变更交付工作台。

## 目标用户

- DBA、数据库运维工程师、变更负责人。
- 需要把变更需求转成标准执行材料的交付团队。
- 需要在面试中展示 AI 产品工程能力和数据库运维经验的人。

## 解决的问题

传统数据库变更交付常见问题是材料分散、风险说明不完整、回滚步骤不清晰、执行前后检查缺少标准化、AI 生成内容不可追溯。这个项目把这些环节收敛到一个受控流程里：

1. 创建变更案例，录入数据库类型、变更目标、SQL、表结构和约束条件。
2. 触发 AI 分析，生成结构化交付物。
3. DBA 人工编辑、查看版本差异并确认交付物。
4. 完成整包签收，导出 Markdown/PDF。
5. 在运行状态页查看 LLM 模式、审计日志、数据库状态和演示就绪情况。

## 核心亮点

- **结构化交付**：输出不是一段回答，而是风险、runbook、回滚、前置检查、验收、沟通摘要等独立交付物。
- **DB2 运维语境**：内置索引变更、加字段、数据修正、REORG/RUNSTATS、锁等待故障等合成案例，离线演示也能体现数据库运维判断。
- **稳定演示**：无 API Key 或模型调用失败时自动使用场景化兜底结果，不会阻断主流程。
- **OpenAI-compatible 适配层**：通过 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 可接入通义千问、DeepSeek 等兼容接口。
- **审计和安全边界**：记录模型调用耗时、状态、失败原因、请求摘要和响应摘要，并在落库前脱敏常见密码、Token、API Key、Authorization/Cookie/session 字段、连接串口令、Webhook URL 密钥和外部响应体敏感字段。
- **人工确认闭环**：支持编辑交付物、保存版本、查看差异、单项确认、整包确认和签收。
- **工单集成闭环**：支持外部工单导入、标准回写 payload、可配置 ITSM Webhook、回写 attempt 日志、失败重试和审计脱敏。
- **可交付证据**：包含 README、架构说明、API 文档、部署说明、演示脚本、样例 Markdown/PDF、截图说明、发布检查表和自动验收脚本。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Alembic。
- 页面：Jinja2 服务端渲染、本地 CSS 和原生增强脚本。
- 数据：SQLite 本地兜底，部署时可切 PostgreSQL。
- AI：OpenAI-compatible HTTP 适配层，支持离线兜底。
- 导出：Markdown 与 PDF。
- 质量保障：pytest、离线 DB2 场景评测、PowerShell 冒烟检查、最终验收脚本、发布就绪审计脚本、GitHub Actions CI。

## 演示路径

本地启动：

```powershell
uvicorn app.main:app --reload
```

建议面试演示顺序：

1. 打开 `http://127.0.0.1:8000/`，说明案例列表、状态和最近生成记录。
2. 进入 `http://127.0.0.1:8000/demo`，选择一个 DB2 合成案例一键生成。
3. 查看一次分析结果，讲解风险、runbook、回滚、检查 SQL 和验收清单。
4. 修改某个交付物，展示版本记录和差异。
5. 单项确认或整包确认，完成签收。
6. 导出 Markdown/PDF，说明这就是可交付材料。
7. 打开 `http://127.0.0.1:8000/ops`，展示健康检查、LLM 模式和审计状态。

## 可验证证据

- 在线演示：`https://dba-changeops-ai-workbench.onrender.com`
- 样例 Markdown：`artifacts/samples/changeops-demo-delivery.md`
- 样例 PDF：`artifacts/samples/changeops-demo-delivery.pdf`
- 架构说明：`docs/ARCHITECTURE.md`
- API 契约：`docs/API.md`
- 部署说明：`docs/DEPLOYMENT.md`
- 演示脚本：`docs/DEMO_SCRIPT.md`
- 面试答辩材料：`docs/INTERVIEW_QA.md`
- 最终交付清单：`docs/HANDOFF_CHECKLIST.md`

验收命令：

```powershell
.\scripts\final_acceptance.ps1 -BaseUrl http://127.0.0.1:8000
.\scripts\release_readiness.ps1 -BaseUrl http://127.0.0.1:8000
```

## 简历表述建议

- 独立设计并实现 DBA ChangeOps AI 工作台，将数据库变更需求自动转化为风险评估、runbook、回滚方案、检查 SQL、验收清单和交付文档。
- 基于 FastAPI、SQLAlchemy、Jinja2、本地 CSS 和原生增强脚本实现完整 Web 工作流，支持案例管理、AI 分析历史、交付物编辑、版本差异、确认签收和 Markdown/PDF 导出。
- 设计 OpenAI-compatible LLM 适配层和离线兜底机制，保证无 API Key 或模型异常时仍可稳定演示，并记录脱敏后的 AI 调用审计日志。
- 围绕 DB2 运维变更场景沉淀合成案例和演示脚本，用工程化方式展示数据库风险控制、回滚设计和交付闭环能力。

## 简历项目经历模板

**DBA ChangeOps AI 工作台 | Python / FastAPI / SQLAlchemy / Jinja2 / OpenAI-compatible LLM**

- 独立完成一款面向数据库运维变更的 AI 交付系统，将变更需求、SQL 和表结构说明转化为风险评估、执行 Runbook、回滚方案、前置检查 SQL、验收清单、沟通摘要和可导出交付包。
- 设计案例、分析运行、交付物、版本记录、LLM 调用日志和工单回写日志等核心数据模型，支持 AI 生成、人工编辑、版本差异、单项确认、整包确认、签收、Webhook 回写、审计脱敏和 Markdown/PDF 导出。
- 实现 OpenAI-compatible 模型适配层，支持通过 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 接入通义千问、DeepSeek 等兼容接口；在无 Key、超时或解析失败时自动启用 DB2 场景化兜底。
- 围绕 DB2 索引变更、新增字段、数据修复、REORG/RUNSTATS、锁等待应急、HADR 受控切换、表空间扩容、权限收敛、备份恢复、SQL 回放验证和分区维护构建合成案例，兼顾公开演示安全边界和数据库运维专业语境。
- 建立 pytest、离线 DB2 场景评测、端到端冒烟、中文 UI 审计、部署配置审计、发布就绪审计和 GitHub Actions CI，覆盖本地演示、打包交付和云部署前验收。

## STAR 讲解稿

**Situation**

数据库变更不是只写 SQL，还需要风险说明、执行步骤、回滚、前后检查、验收和沟通材料。传统材料容易分散，直接用聊天机器人又缺少固定结构、人工复核和审计记录。

**Task**

我希望做一个可以在面试中真实演示的 AI 产品闭环，既体现数据库运维经验，也能展示 Python Web、数据建模、LLM 适配、失败兜底、审计和文档交付能力。

**Action**

我用 FastAPI、SQLAlchemy、Jinja2 和本地 CSS 实现了一个中文 DBA 变更交付工作台。系统把一次变更拆成案例、分析运行、6 类交付物、版本记录和 LLM 调用日志；AI 输出先进入结构化交付物，再由 DBA 编辑、确认、签收，最终导出 Markdown/PDF。为了保证演示稳定，我设计了 OpenAI-compatible 适配层和场景化离线兜底，模型不可用时也会记录失败原因并继续完成流程。

**Result**

项目现在可以完整演示从案例创建、外部工单导入、AI 分析、人工复核、版本追踪、签收、工单回写 payload、ITSM Webhook、失败重试、审计到导出的闭环。本地最终验收覆盖测试、离线评测、Alembic 迁移链、健康检查、演示闭环、导出能力、中文界面、部署配置和交付打包；仓库还包含 Render、Railway、Fly.io、Docker 和 CI 配置，具备继续上线和扩展到真实 DB2 检查的基础。

## 面试开场 60 秒

这个项目叫 DBA ChangeOps AI 工作台。它不是聊天机器人，而是面向数据库运维变更的 AI 交付系统。DBA 做变更时通常不只需要 SQL，还需要风险评估、执行步骤、回滚方案、前置检查、验收清单和沟通材料。我把这些内容做成固定交付物，并加上人工编辑、版本记录、确认、签收和 Markdown/PDF 导出。

技术上我用 FastAPI、SQLAlchemy、Jinja2 和 OpenAI-compatible 适配层实现。模型可用时可以接通义千问、DeepSeek 等兼容接口；没有 Key 或调用失败时，系统会记录审计日志，并用 DB2 场景化兜底内容保证演示不中断。这个项目重点展示的是 AI 产品交付闭环、数据库运维风险控制和工程化验收能力。

## 仍需外部补齐

- 备用演示视频：当前暂缓；后续建议录制 3-5 分钟版本，降低面试现场网络风险。
