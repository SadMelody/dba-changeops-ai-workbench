param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$PythonCommand = "py",
    [string]$TempRoot = ([System.IO.Path]::GetTempPath()),
    [switch]$SkipTests,
    [switch]$SkipCompleteDemo
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$acceptanceRoot = Join-Path $TempRoot "changeops-acceptance"
$acceptanceTemp = Join-Path $acceptanceRoot ([System.Guid]::NewGuid().ToString("n"))
$pytestTemp = Join-Path $acceptanceTemp "pytest"
$oldTemp = $env:TEMP
$oldTmp = $env:TMP

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )

    Write-Step $Label
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Clear-AcceptanceTemp {
    if (Test-Path -LiteralPath $acceptanceTemp) {
        try {
            Remove-Item -LiteralPath $acceptanceTemp -Recurse -Force
        }
        catch {
            Write-Warning "无法清理验收临时目录 $acceptanceTemp：$($_.Exception.Message)"
        }
    }
}

try {
    Clear-AcceptanceTemp
    New-Item -ItemType Directory -Force -Path $acceptanceTemp | Out-Null
    $env:TEMP = $acceptanceTemp
    $env:TMP = $acceptanceTemp

    if (-not $SkipTests) {
        Invoke-Checked "运行自动化测试" {
            & $PythonCommand -B -m pytest -q -p no:cacheprovider --basetemp $pytestTemp
        }
    }

    Write-Step "运行端到端冒烟验收"
    $smokeScript = Join-Path $PSScriptRoot "smoke_check.ps1"
    if ($SkipCompleteDemo) {
        & $smokeScript -BaseUrl $BaseUrl
    }
    else {
        & $smokeScript -BaseUrl $BaseUrl -CompleteDemo
    }
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "运行端到端冒烟验收 failed with exit code $LASTEXITCODE"
    }

    Write-Step "运行中文界面交付审计"
    $uiAuditScript = Join-Path $PSScriptRoot "ui_text_audit.ps1"
    & $uiAuditScript
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "运行中文界面交付审计 failed with exit code $LASTEXITCODE"
    }

    Write-Step "运行部署配置审计"
    $deployAuditScript = Join-Path $PSScriptRoot "deploy_config_audit.ps1"
    & $deployAuditScript
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "运行部署配置审计 failed with exit code $LASTEXITCODE"
    }

    Write-Step "运行面试交付打包检查"
    $packageScript = Join-Path $PSScriptRoot "package_release.ps1"
    $packageOutputDir = Join-Path $acceptanceTemp "changeops-package-check"
    & $packageScript -OutputDir $packageOutputDir -Version "acceptance-check"
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "运行面试交付打包检查 failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "最终验收通过：测试、健康检查、运行状态、演示闭环、导出能力、中文界面、部署配置和交付打包均已确认。"
}
finally {
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    Clear-AcceptanceTemp
}
