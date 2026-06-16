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
    $jsonEnd = $text.LastIndexOf("}")
    $payload = $null
    if ($jsonStart -ge 0 -and $jsonEnd -ge $jsonStart) {
        try {
            $payload = $text.Substring($jsonStart, $jsonEnd - $jsonStart + 1) | ConvertFrom-Json
        }
        catch {
            $payload = $null
        }
    }

    return [pscustomobject]@{
        label = [System.IO.Path]::GetFileName($Path)
        exit_code = $exitCode
        payload = $payload
        raw = $text
    }
}

function Test-ReadyPayload {
    param([pscustomobject]$Result)

    return $Result.exit_code -eq 0 -and $null -ne $Result.payload -and [bool]$Result.payload.ready
}

function Format-RawScriptFailure {
    param(
        [pscustomobject]$Result,
        [int]$MaxLength = 240
    )

    if ([string]::IsNullOrWhiteSpace($Result.raw)) {
        return "$($Result.label) failed with exit code $($Result.exit_code)"
    }

    $lines = @(
        $Result.raw -split "`r?`n" |
            ForEach-Object {
                ($_ -replace "`e\[[0-9;]*[A-Za-z]", "").Trim()
            } |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace($_) -and
                -not $_.StartsWith("==>")
            }
    )

    $detail = if ($lines.Count -gt 0) {
        $lines[-1]
    }
    else {
        ($Result.raw -replace "`e\[[0-9;]*[A-Za-z]", "").Trim()
    }

    if ($detail.Length -gt $MaxLength) {
        $detail = $detail.Substring(0, $MaxLength - 3) + "..."
    }

    return "$($Result.label) failed with exit code $($Result.exit_code): $detail"
}

function Get-JsonScriptDetail {
    param(
        [pscustomobject]$Result,
        [string]$SuccessDetail
    )

    if (Test-ReadyPayload $Result) {
        return $SuccessDetail
    }

    if ($Result.exit_code -ne 0) {
        if ($Result.payload -and $Result.payload.failures) {
            $failedNames = @(
                $Result.payload.failures |
                    ForEach-Object {
                        if ($_.PSObject.Properties["name"]) {
                            $_.name
                        }
                        else {
                            [string]$_
                        }
                    }
            )
            if ($failedNames.Count -gt 0) {
                return "$($Result.label) failed checks: " + ($failedNames -join ", ")
            }
        }
        return Format-RawScriptFailure $Result
    }

    if ($null -eq $Result.payload) {
        return "$($Result.label) did not return parseable JSON"
    }

    if ($Result.payload.failures) {
        $failedNames = @(
            $Result.payload.failures |
                ForEach-Object {
                    if ($_.PSObject.Properties["name"]) {
                        $_.name
                    }
                    else {
                        [string]$_
                    }
                }
        )
        if ($failedNames.Count -gt 0) {
            return "$($Result.label) failed checks: " + ($failedNames -join ", ")
        }
    }

    return "$($Result.label) did not report ready=true"
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

$readmeExists = Test-Path -LiteralPath $ReadmePath
$readme = if ($readmeExists) { Get-Content -LiteralPath $ReadmePath -Raw } else { "" }

function Get-ReadmeReleaseUrl {
    param(
        [string]$Text,
        [string]$Label,
        [string]$MarkdownLabel
    )

    $match = [regex]::Match($Text, "(?m)^$([regex]::Escape($Label))：(?<url>https?://\S+)\s*$")
    if ($match.Success) {
        $url = $match.Groups["url"].Value.Trim().TrimEnd("/")
        if ($url -notmatch "your-app\.example\.com|your-video\.example\.com") {
            return $url
        }
    }

    if ([string]::IsNullOrWhiteSpace($MarkdownLabel)) {
        return $null
    }

    $markdownMatch = [regex]::Match($Text, "\[$([regex]::Escape($MarkdownLabel))\]\((?<url>https?://[^)]+)\)")
    if (-not $markdownMatch.Success) {
        return $null
    }

    $markdownUrl = $markdownMatch.Groups["url"].Value.Trim().TrimEnd("/")
    if ($markdownUrl -match "your-app\.example\.com|your-video\.example\.com") {
        return $null
    }

    return $markdownUrl
}

$inferredDemoUrl = if ($SkipRuntime -and [string]::IsNullOrWhiteSpace($DemoUrl) -and $readmeExists) {
    Get-ReadmeReleaseUrl $readme "在线演示" $null
}
else {
    $null
}

$inferredVideoUrl = if ($SkipRuntime -and [string]::IsNullOrWhiteSpace($VideoUrl) -and $readmeExists) {
    Get-ReadmeReleaseUrl $readme "备用视频" "3-5 分钟备用演示视频"
}
else {
    $null
}

$demoInput = if ($inferredDemoUrl) { $inferredDemoUrl } else { $DemoUrl }
$videoInput = if ($inferredVideoUrl) { $inferredVideoUrl } else { $VideoUrl }

$demo = Normalize-OptionalUrl "DemoUrl" $demoInput
$video = Normalize-OptionalUrl "VideoUrl" $videoInput

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
Add-Check "release:materials" (Test-ReadyPayload $readiness) (Get-JsonScriptDetail $readiness "release materials passed local non-runtime readiness")

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
        Add-Check "online:demo" (Test-ReadyPayload $verify) (Get-JsonScriptDetail $verify "online demo URL passed release verification")
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
        Add-Check "public:delivery-audit" (Test-ReadyPayload $audit) (Get-JsonScriptDetail $audit "public delivery audit passed")
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
    $nextActions.Add("拿到公开视频 URL 后运行：`$VideoUrl = Read-Host `"VideoUrl`"，再运行 scripts/delivery_status.ps1 -DemoUrl https://dba-changeops-ai-workbench.onrender.com -VideoUrl `$VideoUrl -CompleteDemo -Strict。") | Out-Null
}

$failures = @($checks | Where-Object { -not $_.ok })
$strictReady = $failures.Count -eq 0
$strictOnlyCheckNames = @(
    "online:video",
    "online:video-reachable",
    "readme:video-url",
    "public:delivery-audit"
)
$demoBlockingFailures = @(
    $failures |
        Where-Object {
            $strictOnlyCheckNames -notcontains $_.name
        }
)
$demoReady = $demoBlockingFailures.Count -eq 0
$deliveryMode = if ($strictReady) {
    "strict-public"
}
elseif ($demoReady) {
    "demo-only"
}
else {
    "incomplete"
}

$remainingExternalInputs = New-Object System.Collections.Generic.List[string]
if (-not $demo) {
    $remainingExternalInputs.Add("DemoUrl") | Out-Null
}
elseif ($demoBlockingFailures.Count -gt 0) {
    $remainingExternalInputs.Add("verified DemoUrl") | Out-Null
}

if (-not $video) {
    $remainingExternalInputs.Add("VideoUrl") | Out-Null
}
elseif ($failures | Where-Object { $_.name -in @("online:video-reachable", "readme:video-url", "public:delivery-audit") }) {
    $remainingExternalInputs.Add("verified VideoUrl") | Out-Null
}

$statusLabel = if ($deliveryMode -eq "strict-public") {
    "严格公开交付已完成"
}
elseif ($deliveryMode -eq "demo-only") {
    "线上 Demo 和本地材料可展示，严格公开交付仍缺备用视频"
}
else {
    "交付仍有阻塞项，需要先处理失败检查"
}

$result = [pscustomobject]@{
    ready = $strictReady
    demo_ready = $demoReady
    delivery_mode = $deliveryMode
    summary = [pscustomobject]@{
        label = $statusLabel
        strict_public_ready = $strictReady
        demo_ready = $demoReady
        remaining_external_inputs = @($remainingExternalInputs)
    }
    base_url = if ($SkipRuntime) { $null } else { $BaseUrl }
    demo_url = $demo
    demo_url_source = if ($inferredDemoUrl) { "README" } elseif ($demo) { "argument" } else { $null }
    video_url = $video
    video_url_source = if ($inferredVideoUrl) { "README" } elseif ($video) { "argument" } else { $null }
    readme = if ($readmeExists) { (Resolve-Path $ReadmePath).Path } else { $ReadmePath }
    checked_at = (Get-Date).ToString("s")
    checks = $checks
    next_actions = $nextActions
    failures = $failures
    demo_blocking_failures = $demoBlockingFailures
}

$result | ConvertTo-Json -Depth 6

if ($Strict -and $failures.Count -gt 0) {
    exit 1
}
