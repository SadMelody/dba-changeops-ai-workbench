param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$DemoUrl,
    [string]$VideoUrl,
    [string]$ReadmePath = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "README.md"),
    [switch]$SkipRuntime,
    [switch]$CompleteDemo,
    [switch]$AllowHttp,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$checks = New-Object System.Collections.Generic.List[object]
$nextActions = New-Object System.Collections.Generic.List[string]

function Normalize-OptionalUrl {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
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

function Join-Url {
    param([string]$Root, [string]$Path)
    return $Root.TrimEnd("/") + "/" + $Path.TrimStart("/")
}

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )

    $checks.Add([pscustomobject]@{
        name = $Name
        ok = $Ok
        detail = $Detail
    }) | Out-Null
}

function Invoke-JsonScript {
    param(
        [string]$Path,
        [string[]]$Arguments
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing script: $Path"
    }

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $Path @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | Out-String).Trim()
    $jsonStart = $text.IndexOf("{")
    $payload = $null
    if ($jsonStart -ge 0) {
        try {
            $payload = $text.Substring($jsonStart) | ConvertFrom-Json
        }
        catch {
            $payload = $null
        }
    }

    return [pscustomobject]@{
        exit_code = $exitCode
        payload = $payload
        raw = $text
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

$demo = Normalize-OptionalUrl "DemoUrl" $DemoUrl
$video = Normalize-OptionalUrl "VideoUrl" $VideoUrl
$readmeExists = Test-Path -LiteralPath $ReadmePath
$readme = if ($readmeExists) { Get-Content -LiteralPath $ReadmePath -Raw } else { "" }

Add-Check "readme:exists" $readmeExists "README should exist"

if ($readmeExists) {
    Add-Check "readme:release-block" ($readme.Contains("在线演示：") -and $readme.Contains("备用材料：")) "README should expose demo and backup material slots"
    Add-Check "readme:sample-markdown" ($readme.Contains("artifacts/samples/changeops-demo-delivery.md")) "README should link sample Markdown delivery package"
    Add-Check "readme:sample-pdf" ($readme.Contains("artifacts/samples/changeops-demo-delivery.pdf")) "README should link sample PDF delivery package"
}

if (-not $SkipRuntime) {
    try {
        $health = Invoke-RestMethod -Uri (Join-Url $BaseUrl "/healthz") -TimeoutSec 10
        Add-Check "local:healthz" ($health.status -eq "ok" -and $health.database -eq "ok") "local app should report healthy database and service"
    }
    catch {
        Add-Check "local:healthz" $false $_.Exception.Message
    }

    try {
        $status = Invoke-RestMethod -Uri (Join-Url $BaseUrl "/api/system/status") -TimeoutSec 10
        Add-Check "local:demo-cases" ($status.summary.total_cases -ge 5) "local app should contain at least 5 demo cases"
        Add-Check "local:database" ([bool]$status.database_ok) "local app should report database_ok"
    }
    catch {
        Add-Check "local:system-status" $false $_.Exception.Message
    }
}

$readiness = Invoke-JsonScript (Join-Path $PSScriptRoot "release_readiness.ps1") @("-SkipRuntime")
Add-Check "release:materials" ($readiness.exit_code -eq 0) "release materials should pass local non-runtime readiness"

if ($demo) {
    $verifyArgs = @("-BaseUrl", $demo)
    if ($CompleteDemo) {
        $verifyArgs += "-CompleteDemo"
    }
    if ($AllowHttp) {
        $verifyArgs += "-AllowHttp"
    }

    try {
        $verify = Invoke-JsonScript (Join-Path $PSScriptRoot "verify_online_release.ps1") $verifyArgs
        $onlineOk = $verify.exit_code -eq 0 -and $null -ne $verify.payload -and [bool]$verify.payload.ready
        $onlineDetail = "online demo URL should pass release verification"
        if ($null -eq $verify.payload) {
            $onlineDetail = "online verification did not return parseable JSON"
        }
        elseif (-not [bool]$verify.payload.ready -and $verify.payload.failures) {
            $failedNames = @($verify.payload.failures | Select-Object -ExpandProperty name)
            $onlineDetail = "online verification failed: " + ($failedNames -join ", ")
        }
        Add-Check "online:demo" $onlineOk $onlineDetail
    }
    catch {
        Add-Check "online:demo" $false $_.Exception.Message
    }

    if ($readmeExists) {
        Add-Check "readme:demo-url" ($readme.Contains("在线演示：$demo")) "README should include the verified demo URL"
    }
}
else {
    Add-Check "online:demo" $false "DemoUrl is not provided"
    $nextActions.Add("部署到 Render/Railway/Fly.io，拿到真实 HTTPS 在线演示地址；上线后先运行 scripts/verify_online_release.ps1。") | Out-Null
}

if ($video) {
    Add-Check "online:video-reachable" (Test-UrlReachable $video) "backup demo video URL should be reachable"
    if ($readmeExists) {
        Add-Check "readme:video-url" ($readme.Contains($video)) "README should include the backup demo video URL"
    }
}
else {
    Add-Check "online:video" $false "VideoUrl is not provided"
    $nextActions.Add("按 docs/VIDEO_RECORDING_GUIDE.md 录制并上传 3-5 分钟备用演示视频，确保链接无需登录且可被脚本访问。") | Out-Null
}

if ($demo -and $video -and $readmeExists) {
    try {
        $auditArgs = @("-DemoUrl", $demo, "-VideoUrl", $video, "-ReadmePath", $ReadmePath)
        if ($CompleteDemo) {
            $auditArgs += "-CompleteDemo"
        }
        if ($AllowHttp) {
            $auditArgs += "-AllowHttp"
        }
        $audit = Invoke-JsonScript (Join-Path $PSScriptRoot "public_delivery_audit.ps1") $auditArgs
        Add-Check "public:delivery-audit" ($audit.exit_code -eq 0) "public delivery audit should pass"
    }
    catch {
        Add-Check "public:delivery-audit" $false $_.Exception.Message
    }
}
else {
    Add-Check "public:delivery-audit" $false "DemoUrl, VideoUrl, and README are required"
}

if ($demo -and $video -and $readmeExists -and (-not $readme.Contains("在线演示：$demo") -or -not $readme.Contains($video))) {
    $nextActions.Add("运行 scripts/update_release_links.ps1 回填 README 顶部在线演示和视频链接。") | Out-Null
}

if (-not $demo -or -not $video) {
    $nextActions.Add("拿到两个 URL 后运行：scripts/delivery_status.ps1 -DemoUrl <演示地址> -VideoUrl <视频地址> -CompleteDemo -Strict。") | Out-Null
}

$failures = @($checks | Where-Object { -not $_.ok })
$result = [pscustomobject]@{
    ready = $failures.Count -eq 0
    base_url = if ($SkipRuntime) { $null } else { $BaseUrl }
    demo_url = $demo
    video_url = $video
    readme = if ($readmeExists) { (Resolve-Path $ReadmePath).Path } else { $ReadmePath }
    checked_at = (Get-Date).ToString("s")
    checks = $checks
    next_actions = $nextActions
    failures = $failures
}

$result | ConvertTo-Json -Depth 6

if ($Strict -and $failures.Count -gt 0) {
    exit 1
}
