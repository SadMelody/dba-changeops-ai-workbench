param(
    [Parameter(Mandatory = $true)]
    [string]$DemoUrl,
    [Parameter(Mandatory = $true)]
    [string]$VideoUrl,
    [string]$ReadmePath = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "README.md"),
    [switch]$CompleteDemo,
    [switch]$AllowHttp
)

$ErrorActionPreference = "Stop"

function Normalize-Url {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name cannot be empty"
    }

    $url = $Value.Trim().TrimEnd("/")
    if (-not ($url.StartsWith("https://") -or $url.StartsWith("http://"))) {
        throw "$Name must start with http:// or https://"
    }

    if ($url.StartsWith("http://") -and -not $AllowHttp) {
        $isLocal = $url.StartsWith("http://127.0.0.1") -or $url.StartsWith("http://localhost")
        if (-not $isLocal) {
            throw "$Name should use https://. Pass -AllowHttp only for a controlled internal target."
        }
    }

    return $url
}

function Invoke-Script {
    param(
        [string]$Label,
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "==> $Label"
    & pwsh -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode"
    }
}

function Test-UrlReachable {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -Method Head -TimeoutSec 15 -MaximumRedirection 5
        return [int]$response.StatusCode -lt 400
    }
    catch {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 15 -MaximumRedirection 5
            return [int]$response.StatusCode -lt 400
        }
        catch {
            return $false
        }
    }
}

$demo = Normalize-Url "DemoUrl" $DemoUrl
$video = Normalize-Url "VideoUrl" $VideoUrl

if (-not (Test-Path -LiteralPath $ReadmePath)) {
    throw "README not found: $ReadmePath"
}

$verifyScript = Join-Path $PSScriptRoot "verify_online_release.ps1"
$readinessScript = Join-Path $PSScriptRoot "release_readiness.ps1"
if (-not (Test-Path -LiteralPath $verifyScript)) {
    throw "Missing verify script: $verifyScript"
}
if (-not (Test-Path -LiteralPath $readinessScript)) {
    throw "Missing release readiness script: $readinessScript"
}

$verifyArgs = @("-BaseUrl", $demo)
if ($CompleteDemo) {
    $verifyArgs += "-CompleteDemo"
}
if ($AllowHttp) {
    $verifyArgs += "-AllowHttp"
}
Invoke-Script "验证线上演示地址" $verifyScript $verifyArgs

Invoke-Script "验证本地发布材料" $readinessScript @("-SkipRuntime")

$readme = Get-Content -LiteralPath $ReadmePath -Raw
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
    $checks.Add($check) | Out-Null
    if (-not $Ok) {
        $failures.Add($check) | Out-Null
    }
}

Add-Check "readme:demo-url" ($readme.Contains("在线演示：$demo")) "README should include the verified demo URL"
Add-Check "readme:video-url" ($readme.Contains($video)) "README should include the backup demo video URL"
Add-Check "online:video-reachable" (Test-UrlReachable $video) "backup demo video URL should be reachable"
Add-Check "readme:sample-markdown" ($readme.Contains("artifacts/samples/changeops-demo-delivery.md")) "README should link sample Markdown package"
Add-Check "readme:sample-pdf" ($readme.Contains("artifacts/samples/changeops-demo-delivery.pdf")) "README should link sample PDF package"
Add-Check "readme:demo-script" ($readme.Contains("docs/DEMO_SCRIPT.md")) "README should link the 3-5 minute demo script"

$result = [pscustomobject]@{
    ready = $failures.Count -eq 0
    demo_url = $demo
    video_url = $video
    readme = (Resolve-Path $ReadmePath).Path
    complete_demo_checked = [bool]$CompleteDemo
    checked_at = (Get-Date).ToString("s")
    checks = $checks
    failures = $failures
}

Write-Host ""
Write-Host "==> 公开交付审计结果"
$result | ConvertTo-Json -Depth 5

if ($failures.Count -gt 0) {
    exit 1
}
