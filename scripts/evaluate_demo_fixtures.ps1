param(
    [string]$PythonCommand = "py",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Push-Location $projectRoot
try {
    $output = & $PythonCommand -B -m app.evaluation
    if ($LASTEXITCODE -ne 0) {
        throw "离线 DB2 场景评测未通过"
    }
    if ($OutputPath) {
        $resolvedOutput = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
        $parent = Split-Path -Parent $resolvedOutput
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        $output | Set-Content -LiteralPath $resolvedOutput -Encoding UTF8
    }
    $output
}
finally {
    Pop-Location
}
