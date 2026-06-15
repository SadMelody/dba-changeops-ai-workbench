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

function Invoke-ReleaseReadiness {
    $script = Join-Path $Root "scripts\release_readiness.ps1"
    if (-not (Test-Path -LiteralPath $script)) {
        throw "Missing release readiness script: $script"
    }

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $script -SkipRuntime 2>&1
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

$coreDeliveryDocs = @(
    "README.md",
    "docs/COMPLETION_AUDIT.md",
    "docs/HANDOFF_CHECKLIST.md",
    "docs/PUBLIC_DELIVERY.md",
    "docs/RELEASE_CHECKLIST.md"
)

$placeholderPattern = "your-app\.example\.com|your-video\.example\.com|<VideoUrl>|<视频地址>|<演示地址>"

foreach ($path in $coreDeliveryDocs) {
    $fullPath = Join-Path $Root $path
    Add-Check "core-docs:exists:$path" (Test-Path -LiteralPath $fullPath) "core public delivery doc should exist"
    if (Test-Path -LiteralPath $fullPath) {
        $text = Get-Content -LiteralPath $fullPath -Raw
        Add-Check "core-docs:no-placeholder:$path" (-not [regex]::IsMatch($text, $placeholderPattern)) "core public delivery doc should not contain template DemoUrl or VideoUrl examples"
    }
}

$releaseReadiness = Invoke-ReleaseReadiness
Add-Check "release-readiness:exit-zero" ($releaseReadiness.exit_code -eq 0) "release readiness should pass for the current clean workspace"
Add-Check "release-readiness:json" ($null -ne $releaseReadiness.payload) "release readiness should return parseable JSON"

if ($releaseReadiness.payload) {
    $guard = @($releaseReadiness.payload.checks | Where-Object { $_.name -eq "docs:release-url-placeholders" })
    Add-Check "release-readiness:placeholder-guard-present" ($guard.Count -eq 1) "release readiness should expose the public delivery URL placeholder guard"
    if ($guard.Count -eq 1) {
        Add-Check "release-readiness:placeholder-guard-ok" ([bool]$guard[0].ok) "public delivery URL placeholder guard should pass for current docs"
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
