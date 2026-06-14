# 线上发布检查表

这份清单用于把本地演示版收敛成可以投递简历、面试展示或发给面试官查看的在线版本。

## 发布前

1. 确认本地验收通过：

```powershell
.\scripts\final_acceptance.ps1 -BaseUrl http://127.0.0.1:8000
```

该脚本会覆盖自动化测试、离线 DB2 场景评测、Alembic 迁移链、端到端冒烟、中文界面、部署配置和交付打包检查。

2. 如需单独查看离线 DB2 场景评测报告：

```powershell
.\scripts\evaluate_demo_fixtures.ps1 -PythonCommand .\.venv\Scripts\python.exe
```

3. 刷新样例交付包：

```powershell
.\scripts\generate_demo_exports.ps1 -BaseUrl http://127.0.0.1:8000
```

4. 预览并清理本地运行产物：

```powershell
.\scripts\clean_release_artifacts.ps1 -WhatIf
.\scripts\clean_release_artifacts.ps1
```

5. 运行交付就绪审计：

```powershell
.\scripts\release_readiness.ps1 -BaseUrl http://127.0.0.1:8000
```

该审计会在发现 `.env`、本地数据库、日志、进程 pid 文件、Python 缓存或 pytest 缓存残留时失败；如果失败，先重新运行 `scripts/clean_release_artifacts.ps1`。

6. 确认 README 顶部截图和样例链接可打开。
7. 确认 `.env` 没有提交真实密钥。
8. 确认 GitHub Actions CI 通过。

## 部署环境

必填：

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://...
```

可选：

```text
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=...
LLM_MODEL=qwen-plus
ITSM_WEBHOOK_URL=
ITSM_WEBHOOK_TOKEN=
```

如果暂时没有模型 Key，可以不配置 `LLM_API_KEY`。系统会进入离线兜底模式，但仍然能完整生成、确认、签收和导出交付包。
如果暂时没有真实 ITSM Webhook，可以不配置 `ITSM_WEBHOOK_URL`。系统仍可生成回写 payload；主动回写接口会明确返回未配置提示。配置 Webhook 后，每次发送和失败重试都会写入 `work_order_writeback_logs`，便于排查外部系统问题；日志和 API 会保存脱敏后的 Webhook URL 与外部响应体，不会原样展示查询密钥或 Bearer Token。

部署平台变量填写口径：

| 变量 | 是否必填 | 建议值 | 说明 |
| --- | --- | --- | --- |
| `APP_ENV` | 是 | `production` | 用于区分线上运行环境。 |
| `DATABASE_URL` | 是 | `postgresql+psycopg://...` | 使用托管 PostgreSQL；不要使用本地 SQLite。 |
| `LLM_BASE_URL` | 否 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 保留国内 OpenAI-compatible 服务入口。 |
| `LLM_MODEL` | 否 | `qwen-plus` | 真实模型启用时使用。 |
| `LLM_API_KEY` | 否 | 留空或真实 Key | 留空时走离线兜底，更适合稳定公开演示。 |
| `ITSM_WEBHOOK_URL` | 否 | 留空或真实 Webhook | 配置后可主动发送工单回写 payload。 |
| `ITSM_WEBHOOK_TOKEN` | 否 | 留空或真实 Token | 配置后使用 Bearer Token 认证。 |

上线第一版建议先不填 `LLM_API_KEY` 和 `ITSM_WEBHOOK_URL`。这样可以先证明页面、数据库、审计、确认、签收和导出闭环稳定可用；真实模型和真实工单回写可以作为面试中的扩展能力说明。

## 上线后验收

当前线上地址是 `https://dba-changeops-ai-workbench.onrender.com`。如果重新部署到其他平台，再把下面的地址替换成新地址。

```powershell
.\scripts\smoke_check.ps1 -BaseUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo
```

面向公开投递时，建议再运行线上发布验收包装脚本：

```powershell
.\scripts\verify_online_release.ps1 -BaseUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo
```

验收通过后，自动回填 README 顶部发布区：

```powershell
.\scripts\update_release_links.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com
```

最后运行公开交付审计，确认线上地址、视频链接、README 回填和本地发布材料都已就绪：

```powershell
.\scripts\public_delivery_audit.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com -CompleteDemo
```

视频链接需要是面试官无需登录即可访问的公开或半公开地址。审计脚本会实际访问该地址；如果视频链接返回 404、需要登录、权限不足或临时链接过期，就不要投递。

公开投递前，最终状态应该满足：

| 检查项 | 通过标准 |
| --- | --- |
| 线上演示 | `https://.../healthz` 返回 `status: ok` 和 `database: ok`。 |
| 演示闭环 | `scripts/verify_online_release.ps1 -CompleteDemo` 通过。 |
| 运行详情 API | 冒烟脚本确认 `GET /api/runs/{run_id}` 返回交付物、签收状态、LLM 审计和固定导出地址。 |
| 固定交付导出 | 冒烟脚本下载 run 级 Markdown/PDF，确认某一次运行可以稳定归档。 |
| 视频链接 | 无需登录，脚本访问不返回 4xx/5xx。 |
| README | 顶部包含真实在线演示地址和备用视频链接。 |
| 发布审计 | `scripts/delivery_status.ps1 -CompleteDemo -Strict` 返回 `ready: true`。 |

如果还没有拿到线上地址或视频链接，可以先运行状态汇总，看清楚剩余外部事项：

```powershell
.\scripts\delivery_status.ps1 -BaseUrl http://127.0.0.1:8000
.\scripts\delivery_status.ps1 -CompleteDemo -SkipRuntime
.\scripts\delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo -SkipRuntime
```

README 顶部已经回填在线演示地址时，`-SkipRuntime` 会自动读取 `DemoUrl`；显式 `-DemoUrl` 用于检查其他候选部署。

手工检查：

- 首页能打开，且显示中文工作台和 11 个内置 DBA 场景。
- `/demo` 能一键完整闭环。
- `/ops` 显示数据库连接正常、运行状态可用。
- `/healthz` 返回 `status: ok` 和 `database: ok`。
- Markdown 和 PDF 导出可以下载。
- 运行详情页的 Markdown/PDF 导出地址包含 `/runs/{run_id}/`，用于固定归档当前交付包。
- LLM 审计面板能显示真实调用或离线兜底状态。

## README 发布口径

线上地址可用后，在 README 顶部加入：

```markdown
在线演示：<你的线上地址>

备用材料：

- [样例 Markdown 交付包](artifacts/samples/changeops-demo-delivery.md)
- [样例 PDF 交付包](artifacts/samples/changeops-demo-delivery.pdf)
- [3-5 分钟演示脚本](docs/DEMO_SCRIPT.md)
```

如果线上模型 Key 没有配置，可以明确写：

```text
在线演示默认使用离线兜底模式，便于稳定展示完整交付闭环；代码支持通过 OpenAI-compatible 接口接入通义千问、DeepSeek 等模型。
```

## 面试前 30 分钟

- 打开线上首页，确认冷启动完成。
- 打开 `/demo`，提前跑一次“一键完整闭环”。
- 下载一份 PDF，确认中文内容正常。
- 保留本地服务作为备用。
- 准备 3-5 分钟演示视频或本地录屏文件；公开视频地址必须无需登录即可播放或下载。
- 使用 `scripts/update_release_links.ps1` 回填 README 在线演示和视频链接。
- 准备一句兜底说明：模型不可用时系统会保留审计记录，并使用内置 DB2 场景模板保证交付流程不中断。
