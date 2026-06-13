param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$checks = New-Object System.Collections.Generic.List[object]
$failures = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )

    $check = [pscustomobject]@{
        name = $Name
        ok = $Ok
        detail = $Detail
    }
    $checks.Add($check)
    if (-not $Ok) {
        $failures.Add($check)
    }
}

function Read-RequiredText {
    param([string]$Path)

    $fullPath = Join-Path $Root $Path
    if (-not (Test-Path -LiteralPath $fullPath)) {
        Add-Check "file:$Path" $false "required deployment file is missing"
        return ""
    }

    Add-Check "file:$Path" $true "required deployment file exists"
    return Get-Content -LiteralPath $fullPath -Raw
}

function Assert-Contains {
    param(
        [string]$Name,
        [string]$Text,
        [string]$Needle,
        [string]$Detail
    )

    Add-Check $Name ($Text.Contains($Needle)) $Detail
}

$dockerfile = Read-RequiredText "Dockerfile"
$procfile = Read-RequiredText "Procfile"
$render = Read-RequiredText "render.yaml"
$railway = Read-RequiredText "railway.json"
$fly = Read-RequiredText "fly.toml"
$requirements = Read-RequiredText "requirements.txt"
$envExample = Read-RequiredText ".env.example"
$deploymentDoc = Read-RequiredText "docs/DEPLOYMENT.md"

Assert-Contains "docker:python-runtime" $dockerfile "FROM python:" "Dockerfile should declare a Python base image"
Assert-Contains "docker:install-requirements" $dockerfile "pip install --no-cache-dir -r requirements.txt" "Dockerfile should install requirements"
Assert-Contains "docker:app-target" $dockerfile "uvicorn app.main:app" "Dockerfile should start FastAPI app"
Assert-Contains "docker:host" $dockerfile "--host 0.0.0.0" "Dockerfile should bind all interfaces"
Assert-Contains "docker:port-env" $dockerfile '${PORT:-8000}' "Dockerfile should respect platform PORT"

Assert-Contains "procfile:web" $procfile "web:" "Procfile should define a web process"
Assert-Contains "procfile:app-target" $procfile "uvicorn app.main:app" "Procfile should start FastAPI app"
Assert-Contains "procfile:port-env" $procfile '${PORT:-8000}' "Procfile should respect platform PORT"

Assert-Contains "render:python-runtime" $render "runtime: python" "Render config should use Python runtime"
Assert-Contains "render:build-command" $render "pip install -r requirements.txt" "Render config should install dependencies"
Assert-Contains "render:start-command" $render 'uvicorn app.main:app --host 0.0.0.0 --port $PORT' "Render config should use platform PORT"
Assert-Contains "render:health-check" $render "healthCheckPath: /healthz" "Render config should use health check"
Assert-Contains "render:database-url" $render "DATABASE_URL" "Render config should declare database URL"
Assert-Contains "render:llm-base-url" $render "LLM_BASE_URL" "Render config should declare LLM base URL"
Assert-Contains "render:llm-api-key" $render "LLM_API_KEY" "Render config should declare LLM API key"
Assert-Contains "render:llm-model" $render "LLM_MODEL" "Render config should declare LLM model"
Assert-Contains "render:itsm-webhook-url" $render "ITSM_WEBHOOK_URL" "Render config should declare optional ITSM webhook URL"
Assert-Contains "render:itsm-webhook-token" $render "ITSM_WEBHOOK_TOKEN" "Render config should declare optional ITSM webhook token"

Assert-Contains "railway:schema" $railway "railway.schema.json" "Railway config should declare schema"
Assert-Contains "railway:nixpacks" $railway '"builder": "NIXPACKS"' "Railway config should use Nixpacks"
Assert-Contains "railway:start-command" $railway 'uvicorn app.main:app --host 0.0.0.0 --port $PORT' "Railway config should use platform PORT"
Assert-Contains "railway:health-check" $railway '"healthcheckPath": "/healthz"' "Railway config should use health check"
Assert-Contains "railway:restart-policy" $railway '"restartPolicyType": "ON_FAILURE"' "Railway config should restart on failure"

Assert-Contains "fly:app-name" $fly 'app = "dba-changeops-ai-workbench"' "Fly config should declare app name"
Assert-Contains "fly:dockerfile" $fly 'dockerfile = "Dockerfile"' "Fly config should use Dockerfile"
Assert-Contains "fly:internal-port" $fly "internal_port = 8000" "Fly config should route to container port"
Assert-Contains "fly:https" $fly "force_https = true" "Fly config should force HTTPS"
Assert-Contains "fly:health-check" $fly 'path = "/healthz"' "Fly config should use health check"
Assert-Contains "fly:app-env" $fly 'APP_ENV = "production"' "Fly config should set production environment"

Assert-Contains "deps:fastapi" $requirements "fastapi" "requirements should include FastAPI"
Assert-Contains "deps:uvicorn" $requirements "uvicorn" "requirements should include Uvicorn"
Assert-Contains "deps:sqlalchemy" $requirements "sqlalchemy" "requirements should include SQLAlchemy"
Assert-Contains "deps:psycopg" $requirements "psycopg" "requirements should include PostgreSQL driver"
Assert-Contains "deps:httpx" $requirements "httpx" "requirements should include HTTP client for LLM calls"

Assert-Contains "env:database-url" $envExample "DATABASE_URL" ".env.example should document DATABASE_URL"
Assert-Contains "env:llm-base-url" $envExample "LLM_BASE_URL" ".env.example should document LLM_BASE_URL"
Assert-Contains "env:llm-api-key" $envExample "LLM_API_KEY" ".env.example should document LLM_API_KEY"
Assert-Contains "env:llm-model" $envExample "LLM_MODEL" ".env.example should document LLM_MODEL"
Assert-Contains "env:itsm-webhook-url" $envExample "ITSM_WEBHOOK_URL" ".env.example should document ITSM_WEBHOOK_URL"
Assert-Contains "env:itsm-webhook-token" $envExample "ITSM_WEBHOOK_TOKEN" ".env.example should document ITSM_WEBHOOK_TOKEN"

Assert-Contains "docs:render" $deploymentDoc "Render 部署" "deployment docs should explain Render"
Assert-Contains "docs:railway" $deploymentDoc "Railway 部署" "deployment docs should explain Railway"
Assert-Contains "docs:fly" $deploymentDoc "Fly.io 部署" "deployment docs should explain Fly.io"
Assert-Contains "docs:verify-online" $deploymentDoc "verify_online_release.ps1" "deployment docs should mention online verification"

$result = [pscustomobject]@{
    ready = $failures.Count -eq 0
    checked_at = (Get-Date).ToString("s")
    checks = $checks
    failures = $failures
}

$result | ConvertTo-Json -Depth 5

if ($failures.Count -gt 0) {
    exit 1
}
