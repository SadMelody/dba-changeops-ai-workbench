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
    $checks.Add($check) | Out-Null
    if (-not $Ok) {
        $failures.Add($check) | Out-Null
    }
}

function Invoke-DeliveryStatus {
    param([string[]]$Arguments)

    $script = Join-Path $Root "scripts\delivery_status.ps1"
    if (-not (Test-Path -LiteralPath $script)) {
        throw "Missing delivery status script: $script"
    }

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $script @Arguments 2>&1
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
        exit_code = $exitCode
        payload = $payload
        raw = $text
    }
}

function New-TestReadme {
    param([string]$Directory)

    $path = Join-Path $Directory "README.md"
    @"
# DBA ChangeOps AI 工作台

在线演示：
备用材料：

- artifacts/samples/changeops-demo-delivery.md
- artifacts/samples/changeops-demo-delivery.pdf
"@ | Set-Content -LiteralPath $path -Encoding UTF8
    return $path
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("changeops-delivery-status-contract-" + [System.Guid]::NewGuid().ToString("n"))

try {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $readme = New-TestReadme $tempRoot

    $missingInputs = Invoke-DeliveryStatus @("-ReadmePath", $readme, "-SkipRuntime")
    Add-Check "missing-inputs:exit-zero" ($missingInputs.exit_code -eq 0) "non-strict status should return JSON instead of failing the caller"
    Add-Check "missing-inputs:json" ($null -ne $missingInputs.payload) "delivery status should return parseable JSON"

    if ($missingInputs.payload) {
        $remaining = @($missingInputs.payload.summary.remaining_external_inputs)
        $failureNames = @($missingInputs.payload.failures | Select-Object -ExpandProperty name)
        $nextActionsText = (@($missingInputs.payload.next_actions) -join "`n")
        Add-Check "missing-inputs:not-ready" (-not [bool]$missingInputs.payload.ready) "strict public readiness should be false without external URLs"
        Add-Check "missing-inputs:not-demo-ready" (-not [bool]$missingInputs.payload.demo_ready) "demo readiness should be false without DemoUrl"
        Add-Check "missing-inputs:mode" ($missingInputs.payload.delivery_mode -eq "incomplete") "missing DemoUrl and VideoUrl should stay incomplete"
        Add-Check "missing-inputs:demo-url" ($remaining -contains "DemoUrl") "DemoUrl should remain an explicit external input"
        Add-Check "missing-inputs:video-url" ($remaining -contains "VideoUrl") "VideoUrl should remain an explicit external input"
        Add-Check "missing-inputs:online-demo-failure" ($failureNames -contains "online:demo") "online demo check should fail without DemoUrl"
        Add-Check "missing-inputs:online-video-failure" ($failureNames -contains "online:video") "online video check should fail without VideoUrl"
        Add-Check "missing-inputs:public-audit-failure" ($failureNames -contains "public:delivery-audit") "public delivery audit should fail until both URLs are available"
        Add-Check "missing-inputs:copyable-video-action" ($nextActionsText -like "*Read-Host `"VideoUrl`"*") "next action should use a copyable PowerShell VideoUrl prompt"
        Add-Check "missing-inputs:no-angle-placeholder-action" ($nextActionsText -notmatch "<VideoUrl>|<视频地址>|<演示地址>") "next action should not use angle-bracket URL placeholders"
    }

    $httpRejected = Invoke-DeliveryStatus @("-ReadmePath", $readme, "-SkipRuntime", "-DemoUrl", "http://example.test/demo")
    Add-Check "http-url:exit-nonzero" ($httpRejected.exit_code -ne 0) "non-local http DemoUrl should fail unless -AllowHttp is supplied"
    Add-Check "http-url:message" ($httpRejected.raw -like "*DemoUrl should use https://*") "http rejection should explain the HTTPS requirement"
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

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
