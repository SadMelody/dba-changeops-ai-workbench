param(
    [switch]$IncludeSamples,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Resolve-InProject {
    param([string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Path))
    if (-not ($fullPath -eq $projectRoot -or $fullPath.StartsWith($projectRoot + [System.IO.Path]::DirectorySeparatorChar))) {
        throw "Refusing to clean path outside project: $fullPath"
    }
    return $fullPath
}

function Remove-ProjectItem {
    param([string]$Path)

    $fullPath = Resolve-InProject $Path
    if (-not (Test-Path -LiteralPath $fullPath)) {
        return
    }

    if ($WhatIf) {
        Write-Host "Would remove $fullPath"
        return
    }

    Get-ChildItem -LiteralPath $fullPath -Recurse -Force -ErrorAction SilentlyContinue |
        ForEach-Object {
            try {
                $_.Attributes = [System.IO.FileAttributes]::Normal
            }
            catch {
                Write-Warning "Could not reset attributes for $($_.FullName): $($_.Exception.Message)"
            }
        }
    try {
        (Get-Item -LiteralPath $fullPath -Force).Attributes = [System.IO.FileAttributes]::Normal
    }
    catch {
        Write-Warning "Could not reset attributes for ${fullPath}: $($_.Exception.Message)"
    }
    Remove-Item -LiteralPath $fullPath -Recurse -Force
    Write-Host "Removed $fullPath"
}

function Test-SkippedToolPath {
    param([string]$Path)

    $relative = [System.IO.Path]::GetRelativePath($projectRoot, $Path)
    return $relative -like ".venv*" -or $relative -like ".git*" -or $relative -like ".omx*"
}

$paths = @(
    ".pytest_cache",
    "pytest-cache-files-*",
    "changeops.db",
    "changeops.db-journal",
    "smoke.db",
    "smoke.db-journal",
    "uri_smoke.db",
    "uri_smoke.db-journal",
    "changeops-ci.db",
    "changeops-ci.db-journal",
    "uvicorn.log",
    "uvicorn.out.log",
    "uvicorn.err.log",
    "uvicorn-ci.log",
    "uvicorn-ci.pid",
    "artifacts\tmp"
)

foreach ($path in $paths) {
    $matches = Get-ChildItem -Path $projectRoot -Force -Filter $path -ErrorAction SilentlyContinue
    if ($matches) {
        foreach ($match in $matches) {
            $relative = [System.IO.Path]::GetRelativePath($projectRoot, $match.FullName)
            Remove-ProjectItem $relative
        }
    }
    else {
        Remove-ProjectItem $path
    }
}

Get-ChildItem -Path $projectRoot -Directory -Recurse -Force -Filter "__pycache__" |
    Where-Object { -not (Test-SkippedToolPath $_.FullName) } |
    ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($projectRoot, $_.FullName)
        Remove-ProjectItem $relative
    }

Get-ChildItem -Path $projectRoot -Recurse -Force -Include "*.pyc", "*.pyo" |
    Where-Object { -not (Test-SkippedToolPath $_.FullName) } |
    ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($projectRoot, $_.FullName)
        Remove-ProjectItem $relative
    }

if ($IncludeSamples) {
    Remove-ProjectItem "artifacts/samples"
}

if ($WhatIf) {
    Write-Host "Clean preview complete."
}
else {
    Write-Host "Release artifact cleanup complete."
}
