param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,
    [switch]$CompleteDemo,
    [switch]$AllowHttp
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Add-Check {
    param(
        [System.Collections.Generic.List[object]]$Checks,
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )

    $Checks.Add([pscustomobject]@{
        name = $Name
        ok = $Ok
        detail = $Detail
    }) | Out-Null
}

function Convert-SmokeOutput {
    param([object[]]$Output)

    $text = ($Output | Out-String).Trim()
    $jsonStart = $text.IndexOf("{")
    $jsonEnd = $text.LastIndexOf("}")
    if ($jsonStart -lt 0 -or $jsonEnd -lt $jsonStart) {
        throw "Smoke check did not return JSON output: $text"
    }

    return $text.Substring($jsonStart, $jsonEnd - $jsonStart + 1) | ConvertFrom-Json
}

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    throw "BaseUrl cannot be empty"
}

$normalizedBaseUrl = $BaseUrl.Trim().TrimEnd("/")
if (-not ($normalizedBaseUrl.StartsWith("https://") -or $normalizedBaseUrl.StartsWith("http://"))) {
    throw "BaseUrl must start with http:// or https://"
}

if ($normalizedBaseUrl.StartsWith("http://") -and -not $AllowHttp) {
    $isLocal = $normalizedBaseUrl.StartsWith("http://127.0.0.1") -or
        $normalizedBaseUrl.StartsWith("http://localhost")
    if (-not $isLocal) {
        throw "Online release URL should use https://. Pass -AllowHttp only for a controlled internal target."
    }
}

$smokeScript = Join-Path $PSScriptRoot "smoke_check.ps1"
if (-not (Test-Path -LiteralPath $smokeScript)) {
    throw "Missing smoke script: $smokeScript"
}

Write-Step "验证线上服务冒烟路径"
$smokeOutput = $null
if ($CompleteDemo) {
    $smokeOutput = & $smokeScript -BaseUrl $normalizedBaseUrl -CompleteDemo
}
else {
    $smokeOutput = & $smokeScript -BaseUrl $normalizedBaseUrl
}
if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "Online smoke check failed with exit code $LASTEXITCODE"
}

$smoke = Convert-SmokeOutput $smokeOutput
$checks = New-Object System.Collections.Generic.List[object]
Add-Check $checks "online:healthz" ($smoke.health -eq "ok" -and $smoke.database -eq "ok") "healthz should report ok service and database"
Add-Check $checks "online:system-status" ([int]$smoke.total_cases -ge 5) "system status should expose seeded DBA demo cases"
Add-Check $checks "online:ops-page" ([bool]$smoke.ops_page) "/ops should render the operational status page"
Add-Check $checks "online:demo-page" ([bool]$smoke.demo_page) "/demo should render the guided demo page"

if ($CompleteDemo) {
    Add-Check $checks "online:complete-demo" ([bool]$smoke.demo_complete) "demo should create a signed delivery package"
    Add-Check $checks "online:run-detail-api" ([bool]$smoke.run_detail_api) "run detail API should expose delivery, signoff, artifacts, and audit logs"
    Add-Check $checks "online:markdown-export" ([bool]$smoke.export_markdown -and [bool]$smoke.run_export_markdown) "case and run-scoped Markdown exports should download"
    Add-Check $checks "online:pdf-export" ([bool]$smoke.export_pdf -and [bool]$smoke.run_export_pdf) "case and run-scoped PDF exports should download"
}

$failures = @($checks | Where-Object { -not $_.ok })
$result = [pscustomobject]@{
    ready = $failures.Count -eq 0
    base_url = $normalizedBaseUrl
    checked_at = (Get-Date).ToString("s")
    complete_demo_checked = [bool]$CompleteDemo
    smoke = $smoke
    checks = $checks
    next_manual_checks = @(
        "把线上地址回填到 README 顶部的在线演示位置",
        "打开线上首页和 /demo，确认中文界面截图与实际页面一致",
        "下载一份 Markdown 和 PDF，确认浏览器下载正常",
        "录制或更新 3-5 分钟备用演示视频",
        "公开视频不要包含真实密钥、真实数据库地址或公司内部数据"
    )
    failures = $failures
}

Write-Step "线上交付验收结果"
$result | ConvertTo-Json -Depth 4

if ($failures.Count -gt 0) {
    exit 1
}
