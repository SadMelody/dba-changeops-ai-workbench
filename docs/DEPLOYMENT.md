# 部署清单

## 部署目标

DBA ChangeOps AI 工作台需要满足两个演示场景：

- 本地试运行：无模型 Key 也能完整跑通，适合网络或额度不可用时兜底。
- 在线演示：部署到 Render/Railway/Fly.io，并连接托管 PostgreSQL。

在线部署不是为了追求复杂运维，而是为了验证项目具备交付意识：环境变量、健康检查、数据库连接、启动命令和失败兜底都已经考虑。

## 公开投递最短路径

如果目标是尽快拿到可以放进简历、作品集和面试材料的公开地址，优先按这个顺序做：

1. 把当前仓库推送到 GitHub。
2. 在 Render、Railway 或 Fly.io 中任选一个平台创建 Web 服务。
3. 绑定 PostgreSQL，配置 `DATABASE_URL`。
4. 先不配置 `LLM_API_KEY`，让线上演示稳定使用离线兜底模式。
5. 部署后打开 `https://.../healthz`，确认 `status` 和 `database` 都是 `ok`。
6. 打开 `https://.../demo`，点击“一键完整闭环”，确认可生成、确认、签收并导出。
7. 录制 3-5 分钟演示视频，并上传到无需登录即可访问的地址；如果视频暂缓，可以先跳过。
8. 回填 README 顶部在线演示链接；视频暂缓时只回填 `DemoUrl`。
9. 运行公开交付审计，确认线上地址、视频地址和 README 都已就绪。

回填和审计命令：

```powershell
$VideoUrl = Read-Host "VideoUrl"
.\scripts\update_release_links.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -VideoUrl $VideoUrl
.\scripts\delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -VideoUrl $VideoUrl -CompleteDemo -Strict
```

这条路径的原则是先证明产品闭环可在线打开，再决定是否接入真实模型。真实模型可以作为增强项，不应阻塞公开投递。
当前 Render DemoUrl 为 `https://dba-changeops-ai-workbench.onrender.com`。视频暂缓时，使用非严格状态汇总确认 Demo 和本地材料即可：

```powershell
.\scripts\delivery_status.ps1 -CompleteDemo -SkipRuntime
.\scripts\delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo -SkipRuntime
```

README 顶部已经回填在线演示地址时，第一条命令会自动读取该地址；第二条命令用于显式检查其他部署地址。

## 本地预检

```powershell
python -m pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

面试现场如果只需要稳定本地演示，可以用内存数据库启动备用服务：

```powershell
$env:DATABASE_URL = "sqlite:///:memory:"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

该方式不写本地 SQLite 文件，适合规避 Windows 权限、路径或文件锁问题；云部署仍应配置 `DATABASE_URL` 使用 PostgreSQL。

打开：

```text
http://127.0.0.1:8000
```

检查：

- 首页至少能看到 11 个内置 DBA 演示案例。
- 点击“生成交付方案”能进入结果页。
- `/healthz` 返回 `status: ok` 和 `database: ok`。
- `/ops` 显示“可交付试运行”、交付签收统计，并能打开 `/api/system/status`。
- 无 `LLM_API_KEY` 时仍能生成离线兜底结果。

## 环境变量

必需：

```text
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
```

推荐：

```text
APP_ENV=production
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your-api-key
LLM_MODEL=qwen-plus
ITSM_WEBHOOK_URL=https://itsm.example.test/webhook/changeops
ITSM_WEBHOOK_TOKEN=your-webhook-token
```

说明：

- `LLM_API_KEY` 可以为空，系统会进入离线兜底模式。
- `ITSM_WEBHOOK_URL` 可以为空，系统仍可生成工单回写 payload；配置后才会主动发送 Webhook，并记录发送/失败重试 attempt。
- `ITSM_WEBHOOK_TOKEN` 可以为空；配置后主动回写请求会带 `Authorization: Bearer <token>`。
- 如果使用 Supabase/Neon/Railway 的 PostgreSQL，优先复制官方提供的连接串，再确认协议前缀是 `postgresql+psycopg://`。
- 如果平台提供的是 `postgres://` 或 `postgresql://`，需要按 SQLAlchemy/psycopg 连接格式调整。

## Render 部署

仓库已提供 `render.yaml`，可以使用 Render Blueprint。

步骤：

1. 将代码推送到 GitHub。
2. 在 Render 选择 Blueprint 或 Web Service。
3. 如果使用 Blueprint，选择仓库中的 `render.yaml`。
4. 配置 `DATABASE_URL`。
5. 如需真实模型，配置 `LLM_API_KEY`。
6. 如需真实工单回写，配置 `ITSM_WEBHOOK_URL` 和 `ITSM_WEBHOOK_TOKEN`。
7. 部署后打开服务地址。
8. 检查 `/healthz` 和 `/ops`。

手动配置时：

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /healthz
```

## Railway 部署

仓库已提供 `railway.json` 和 `Procfile`。`railway.json` 指定 Nixpacks 构建、Web 启动命令、`/healthz` 健康检查和失败重启策略；`Procfile` 作为兼容兜底。

步骤：

1. 新建 Railway Project。
2. 连接 GitHub 仓库。
3. 添加 PostgreSQL 服务。
4. 将 PostgreSQL 连接串配置为 `DATABASE_URL`。
5. 配置模型环境变量。
6. 部署完成后访问根路径、`/healthz` 和 `/ops`。

如果 Railway 没有自动识别启动命令，手动设置：

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Fly.io 部署

仓库已提供 `fly.toml`，默认使用 `Dockerfile` 构建容器镜像，内部端口为 `8000`，健康检查路径为 `/healthz`。

推荐流程：

```bash
fly launch --copy-config
fly secrets set DATABASE_URL="postgresql+psycopg://..."
fly secrets set LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
fly secrets set LLM_API_KEY="your-api-key"
fly secrets set LLM_MODEL="qwen-plus"
fly secrets set ITSM_WEBHOOK_URL="https://itsm.example.test/webhook/changeops"
fly secrets set ITSM_WEBHOOK_TOKEN="your-webhook-token"
fly deploy
```

如果只做产品试运行，也可以先不设置 `LLM_API_KEY`，保留离线兜底。
如果暂时没有真实工单系统，也可以先不设置 `ITSM_WEBHOOK_URL`，只展示回写 payload。

## 部署后验收

上线后按以下顺序检查：

1. 打开 `/healthz`，确认返回 `status: ok`。
2. 打开 `/ops`，确认运行状态、数据库、模型模式、案例统计和签收统计。
3. 打开首页，确认至少 11 个内置演示案例已写入。
4. 打开 `/demo`，确认交付演示台可用。
5. 点击“一键生成交付包”，或点击“一键完整闭环”快速生成已确认、已签收交付包。
6. 查看 LLM 调用审计，确认是真实模型或离线兜底。
7. 查看交付完成度，确认待复核项数量。
8. 编辑一份交付物并确认，查看完成度变化和版本记录。
9. 点击“确认全部交付物”，确认交付包进入可导出状态。
10. 点击“签收交付包”，确认页面显示签收人、签收时间和签收说明。
11. 导出 Markdown。
12. 导出 PDF。

也可以用脚本做一次自动化冒烟检查：

```powershell
.\scripts\smoke_check.ps1 -BaseUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo
```

不加 `-CompleteDemo` 时只检查健康状态、运行状态页、状态 API 和演示台入口；加上后会额外跑一键完整闭环并校验 Markdown/PDF 导出。

如果是面向简历或面试的公开发布，建议使用发布包装脚本：

```powershell
.\scripts\verify_online_release.ps1 -BaseUrl https://dba-changeops-ai-workbench.onrender.com -CompleteDemo
```

它会复用冒烟检查，并提醒回填 README 在线演示地址、下载导出文件、更新备用演示视频和避免公开敏感信息。

## 现场讲解前检查

建议现场讲解前 30 分钟完成：

- 本地服务能启动。
- 在线地址能打开。
- `/healthz` 正常。
- `/ops` 显示可交付试运行。
- 至少一个案例已经生成过交付方案。
- 准备好无 Key 兜底讲解。
- 准备好真实模型失败时的解释：系统会记录失败原因，并继续产出演示结果。
- 准备好 3-5 分钟产品讲解脚本：`docs/DEMO_SCRIPT.md`。

## 常见问题

### 部署后首页 500

优先检查 `DATABASE_URL` 是否正确，尤其是协议前缀和密码里的特殊字符是否需要 URL 编码。

### 健康检查失败

访问 `/healthz`，如果返回 `database: error`，说明 Web 服务已启动但数据库连接失败。检查数据库网络、账号、密码和连接串。

### 运行状态不满足

访问 `/ops` 查看具体检查项。常见原因是合成案例未写入、数据库连接异常，或还没有生成任何交付方案。`/api/system/status` 可用于部署平台或脚本做自动化核验。

### 模型调用失败

系统会自动使用离线兜底，并在 LLM 调用审计中记录失败原因。讲解时可以把这作为可靠性设计点说明。

### PDF 导出检查

PDF 导出使用内置中文字体声明和结构化文本排版，内容包含文档封面、目录、交付清单、签收记录、版本记录、审计摘要和页码，适合产品讲解与变更评审预览。部署后如果浏览器预览中文异常，先下载到本地 PDF 阅读器打开；如果仍异常，再检查部署平台是否改写了响应头或文件内容。
