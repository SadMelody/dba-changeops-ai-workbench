# 公开投递操作单

本文件用于最后一次投递前执行，目标是把 DBA ChangeOps AI 工作台从“本地可演示”推进到“面试官可打开、可复核、可备用播放”的公开作品。

## 当前状态

本地交付闭环已经完成：

- 中文工作台：案例、详情、演示台、运行状态页。
- AI 工作流：OpenAI-compatible 适配、离线兜底、审计日志、脱敏。
- 交付闭环：风险、Runbook、回滚、前置检查 SQL、验收清单、沟通摘要。
- 人工复核：编辑、确认、版本记录、差异查看、整包签收。
- 导出材料：Markdown、PDF、样例交付包和截图。
- 验收门禁：测试、冒烟、中文 UI 审计、部署配置审计、发布就绪审计。

仍需要外部补齐：

- 一个真实 HTTPS 在线演示地址。
- 一个无需登录即可访问的 3-5 分钟备用演示视频地址。

## 最短上线顺序

1. 把代码推送到 GitHub。
2. 在 Render、Railway 或 Fly.io 创建 Web 服务。
3. 绑定 PostgreSQL，填写 `DATABASE_URL`。
4. 第一版公开演示建议不填 `LLM_API_KEY`，让系统稳定走离线兜底。
5. 等部署完成，打开：

```text
https://your-app.example.com/
https://your-app.example.com/demo
https://your-app.example.com/ops
https://your-app.example.com/healthz
```

6. 在线验收：

```powershell
.\scripts\verify_online_release.ps1 -BaseUrl https://your-app.example.com -CompleteDemo
```

7. 按 `docs/VIDEO_RECORDING_GUIDE.md` 录制 3-5 分钟视频，并上传到无需登录即可访问的位置。
8. 回填 README 顶部链接：

```powershell
.\scripts\update_release_links.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com
```

9. 最终公开交付审计：

```powershell
.\scripts\delivery_status.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com -CompleteDemo -Strict
```

只有上面命令返回 `ready: true`，才算严格意义上的公开投递完成。

## 平台环境变量

| 变量 | 建议值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `production` | 标记线上环境。 |
| `DATABASE_URL` | `postgresql+psycopg://...` | 必填，使用部署平台或托管 PostgreSQL 提供的连接串。 |
| `LLM_BASE_URL` | 留空或兼容接口地址 | 第一版可留空。 |
| `LLM_MODEL` | `qwen-plus` 或 `deepseek-chat` | 配置真实模型时填写。 |
| `LLM_API_KEY` | 留空或真实 Key | 第一版建议留空，避免额度、网络和供应商状态影响演示。 |

## 录屏检查

录制时只展示合成案例，不展示真实公司系统、真实数据库地址、真实密钥或真实业务数据。

建议视频路径：

1. 首页说明产品定位和交付就绪度。
2. 打开 `/demo`，使用推荐 DB2 案例一键完整闭环。
3. 展示 6 类交付物、LLM 审计、人工确认、版本记录和签收。
4. 导出 Markdown/PDF。
5. 打开 `/ops`，说明线上健康检查和交付统计。
6. 结尾说明这是一个可继续接入真实工单和 DB2 检查 SQL 的 AI 运维产品骨架。

## 投递前自查

```powershell
.\scripts\release_readiness.ps1 -SkipRuntime
.\scripts\deploy_config_audit.ps1
.\scripts\delivery_status.ps1 -DemoUrl https://your-app.example.com -VideoUrl https://your-video.example.com -CompleteDemo -Strict
```

投递材料应至少包含：

- GitHub 仓库地址。
- README 顶部的在线演示地址。
- README 顶部的备用视频地址。
- 样例 Markdown/PDF 交付包。
- `docs/PORTFOLIO_BRIEF.md` 一页式项目介绍。
- `docs/DEMO_SCRIPT.md` 3-5 分钟演示脚本。
- `docs/INTERVIEW_QA.md` 面试答辩材料。
