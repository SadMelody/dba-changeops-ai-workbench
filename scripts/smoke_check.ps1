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
    run_detail_api = $false
    export_markdown = $false
    export_pdf = $false
    run_export_markdown = $false
    run_export_pdf = $false
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
    $runId = ($location -split "/")[4]
    if (-not $caseId -or -not $runId) {
        throw "Unable to parse case id and run id from Location: $location"
    }

    $runDetail = Invoke-RestMethod -Uri (Join-Url $BaseUrl "/api/runs/$runId")
    if ([int]$runDetail.id -ne [int]$runId) {
        throw "Run detail API returned unexpected id: $($runDetail.id)"
    }
    if ([int]$runDetail.case.id -ne [int]$caseId) {
        throw "Run detail API returned unexpected case id: $($runDetail.case.id)"
    }
    if (-not $runDetail.delivery.is_complete -or -not $runDetail.signoff.is_signed) {
        throw "Run detail API should expose a complete signed delivery package"
    }
    if (@($runDetail.artifacts).Count -lt 6) {
        throw "Run detail API should include at least 6 artifacts"
    }
    if (@($runDetail.llm_logs).Count -lt 1) {
        throw "Run detail API should include LLM audit logs"
    }
    $expectedMarkdownUrl = "/cases/$caseId/runs/$runId/export"
    $expectedPdfUrl = "/cases/$caseId/runs/$runId/export.pdf"
    if ($runDetail.export_urls.markdown -ne $expectedMarkdownUrl -or
        $runDetail.export_urls.pdf -ne $expectedPdfUrl) {
        throw "Run detail API should expose run-scoped export URLs"
    }

    $markdown = Invoke-WebRequest -Uri (Join-Url $BaseUrl "/cases/$caseId/export")
    Assert-Contains $markdown.Content "DBA ChangeOps AI 变更交付包" "markdown export"
    Assert-Contains $markdown.Content "签收状态：已签收" "markdown export"

    $runMarkdown = Invoke-WebRequest -Uri (Join-Url $BaseUrl $expectedMarkdownUrl)
    Assert-Contains $runMarkdown.Content "DBA ChangeOps AI 变更交付包" "run markdown export"
    Assert-Contains $runMarkdown.Content ("CHANGEOPS-{0:D4}-RUN-{1:D4}" -f [int]$caseId, [int]$runId) "run markdown export"
    Assert-Contains $runMarkdown.Content "签收状态：已签收" "run markdown export"

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

    $runPdfPath = Join-Path ([System.IO.Path]::GetTempPath()) "changeops-smoke-run-export.pdf"
    Invoke-WebRequest -Uri (Join-Url $BaseUrl $expectedPdfUrl) -OutFile $runPdfPath
    $runPdfBytes = [System.IO.File]::ReadAllBytes($runPdfPath)
    if ($runPdfBytes.Length -lt 5) {
        throw "Run-scoped PDF export is unexpectedly small"
    }
    $runPdfHeader = [System.Text.Encoding]::ASCII.GetString($runPdfBytes, 0, 4)
    if ($runPdfHeader -ne "%PDF") {
        throw "Run-scoped PDF export did not start with %PDF"
    }
    Remove-Item -LiteralPath $runPdfPath -Force

    $result.demo_complete = $true
    $result.run_detail_api = $true
    $result.export_markdown = $true
    $result.export_pdf = $true
    $result.run_export_markdown = $true
    $result.run_export_pdf = $true
}

[pscustomobject]$result | ConvertTo-Json -Compress
