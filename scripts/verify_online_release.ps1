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
if ($CompleteDemo) {
    & $smokeScript -BaseUrl $normalizedBaseUrl -CompleteDemo
}
else {
    & $smokeScript -BaseUrl $normalizedBaseUrl
}
if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "Online smoke check failed with exit code $LASTEXITCODE"
}

$result = [pscustomobject]@{
    ready = $true
    base_url = $normalizedBaseUrl
    checked_at = (Get-Date).ToString("s")
    complete_demo_checked = [bool]$CompleteDemo
    next_manual_checks = @(
        "把线上地址回填到 README 顶部的在线演示位置",
        "打开线上首页和 /demo，确认中文界面截图与实际页面一致",
        "下载一份 Markdown 和 PDF，确认浏览器下载正常",
        "录制或更新 3-5 分钟备用演示视频",
        "公开视频不要包含真实密钥、真实数据库地址或公司内部数据"
    )
}

Write-Step "线上交付验收结果"
$result | ConvertTo-Json -Depth 4
