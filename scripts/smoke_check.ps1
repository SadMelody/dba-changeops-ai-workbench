param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$CompleteDemo
)

$ErrorActionPreference = "Stop"

function Join-Url {
    param([string]$Root, [string]$Path)
    return $Root.TrimEnd("/") + "/" + $Path.TrimStart("/")
}

function Assert-Contains {
    param([string]$Content, [string]$Expected, [string]$Name)
    if (-not $Content.Contains($Expected)) {
        throw "$Name missing expected text: $Expected"
    }
}

function Invoke-PostNoRedirect {
    param([string]$Uri)

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    try {
        $response = $client.PostAsync($Uri, $null).GetAwaiter().GetResult()
        return $response
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

$health = Invoke-RestMethod -Uri (Join-Url $BaseUrl "/healthz")
if ($health.status -ne "ok" -or $health.database -ne "ok") {
    throw "Health check failed: $($health | ConvertTo-Json -Compress)"
}

$status = Invoke-RestMethod -Uri (Join-Url $BaseUrl "/api/system/status")
if (-not $status.database_ok) {
    throw "Database readiness failed: $($status | ConvertTo-Json -Compress)"
}
if ($status.summary.total_cases -lt 5) {
    throw "Expected at least 5 demo cases, got $($status.summary.total_cases)"
}

$ops = Invoke-WebRequest -Uri (Join-Url $BaseUrl "/ops")
Assert-Contains $ops.Content "运行状态" "/ops page"
Assert-Contains $ops.Content "交付核验" "/ops page"

$demo = Invoke-WebRequest -Uri (Join-Url $BaseUrl "/demo")
Assert-Contains $demo.Content "交付演示台" "/demo page"
Assert-Contains $demo.Content "一键完整闭环" "/demo page"

$result = [ordered]@{
    base_url = $BaseUrl
    health = "ok"
    database = "ok"
    total_cases = $status.summary.total_cases
    llm_mode = $status.llm_mode_label
    demo_complete = $false
    export_markdown = $false
    export_pdf = $false
}

if ($CompleteDemo) {
    $complete = Invoke-PostNoRedirect -Uri (Join-Url $BaseUrl "/demo/complete")
    if ([int]$complete.StatusCode -ne 303) {
        throw "Expected /demo/complete to return 303, got $([int]$complete.StatusCode)"
    }
    $location = [string]$complete.Headers.Location
    if (-not $location) {
        throw "Demo complete did not return a Location header"
    }

    $runPage = Invoke-WebRequest -Uri (Join-Url $BaseUrl $location)
    Assert-Contains $runPage.Content "6/6 已确认" "run page"
    Assert-Contains $runPage.Content "已签收" "run page"

    $caseId = ($location -split "/")[2]
    $markdown = Invoke-WebRequest -Uri (Join-Url $BaseUrl "/cases/$caseId/export")
    Assert-Contains $markdown.Content "DBA ChangeOps AI 变更交付包" "markdown export"
    Assert-Contains $markdown.Content "签收状态：已签收" "markdown export"

    $pdfPath = Join-Path ([System.IO.Path]::GetTempPath()) "changeops-smoke-export.pdf"
    Invoke-WebRequest -Uri (Join-Url $BaseUrl "/cases/$caseId/export.pdf") -OutFile $pdfPath
    $pdfBytes = [System.IO.File]::ReadAllBytes($pdfPath)
    if ($pdfBytes.Length -lt 5) {
        throw "PDF export is unexpectedly small"
    }
    $pdfHeader = [System.Text.Encoding]::ASCII.GetString($pdfBytes, 0, 4)
    if ($pdfHeader -ne "%PDF") {
        throw "PDF export did not start with %PDF"
    }
    Remove-Item -LiteralPath $pdfPath -Force

    $result.demo_complete = $true
    $result.export_markdown = $true
    $result.export_pdf = $true
}

[pscustomobject]$result | ConvertTo-Json -Compress
