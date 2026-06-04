param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$OutputDir = "artifacts/samples"
)

$ErrorActionPreference = "Stop"

function Join-Url {
    param([string]$Root, [string]$Path)
    return $Root.TrimEnd("/") + "/" + $Path.TrimStart("/")
}

function Invoke-PostNoRedirect {
    param([string]$Uri)

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    try {
        return $client.PostAsync($Uri, $null).GetAwaiter().GetResult()
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$complete = Invoke-PostNoRedirect -Uri (Join-Url $BaseUrl "/demo/complete")
if ([int]$complete.StatusCode -ne 303) {
    throw "Expected /demo/complete to return 303, got $([int]$complete.StatusCode)"
}

$location = [string]$complete.Headers.Location
if (-not $location) {
    throw "Demo complete did not return a Location header"
}

$caseId = ($location -split "/")[2]
$markdownPath = Join-Path $OutputDir "changeops-demo-delivery.md"
$pdfPath = Join-Path $OutputDir "changeops-demo-delivery.pdf"

Invoke-WebRequest -Uri (Join-Url $BaseUrl "/cases/$caseId/export") -OutFile $markdownPath
Invoke-WebRequest -Uri (Join-Url $BaseUrl "/cases/$caseId/export.pdf") -OutFile $pdfPath

$markdown = Get-Item -LiteralPath $markdownPath
$pdf = Get-Item -LiteralPath $pdfPath

[pscustomobject]@{
    base_url = $BaseUrl
    run_url = (Join-Url $BaseUrl $location)
    case_id = $caseId
    markdown = $markdown.FullName
    markdown_bytes = $markdown.Length
    pdf = $pdf.FullName
    pdf_bytes = $pdf.Length
} | ConvertTo-Json -Compress
