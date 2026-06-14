param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$OutputDir = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "artifacts\releases"),
    [string]$Name = "dba-changeops-ai-workbench",
    [string]$Version = (Get-Date).ToString("yyyyMMdd-HHmmss")
)

$ErrorActionPreference = "Stop"

function Test-ExcludedPath {
    param([string]$RelativePath)

    $path = $RelativePath.Replace("\", "/")
    $segments = $path.Split("/")

    if ($segments -contains ".git") { return $true }
    if ($segments -contains ".omx") { return $true }
    if ($segments -contains ".venv") { return $true }
    if ($segments -contains "__pycache__") { return $true }
    if ($segments -contains ".pytest_cache") { return $true }
    if ($path.StartsWith("pytest-cache-files-")) { return $true }
    if ($path.StartsWith("outputs/")) { return $true }
    if ($path.StartsWith("artifacts/tmp/")) { return $true }
    if ($path.StartsWith("artifacts/releases/")) { return $true }

    if ($path -eq ".env") { return $true }
    if ($path.EndsWith(".pyc")) { return $true }
    if ($path.EndsWith(".pyo")) { return $true }
    if ($path.EndsWith(".db")) { return $true }
    if ($path.EndsWith(".db-journal")) { return $true }
    if ($path.EndsWith(".log")) { return $true }
    if ($path.EndsWith(".pid")) { return $true }

    return $false
}

function Get-RelativePath {
    param([string]$Path)
    return [System.IO.Path]::GetRelativePath($Root, $Path)
}

function Get-PackageFiles {
    param([string]$StartPath)

    $pending = New-Object System.Collections.Generic.Stack[string]
    $pending.Push($StartPath)

    while ($pending.Count -gt 0) {
        $current = $pending.Pop()

        foreach ($directory in Get-ChildItem -LiteralPath $current -Directory -Force) {
            $relativeDirectory = (Get-RelativePath $directory.FullName).Replace("\", "/").TrimEnd("/") + "/"
            if (-not (Test-ExcludedPath $relativeDirectory)) {
                $pending.Push($directory.FullName)
            }
        }

        foreach ($file in Get-ChildItem -LiteralPath $current -File -Force) {
            $relativeFile = Get-RelativePath $file.FullName
            if (-not (Test-ExcludedPath $relativeFile)) {
                $file
            }
        }
    }
}

$rootPath = [System.IO.Path]::GetFullPath($Root)
$outputPath = [System.IO.Path]::GetFullPath($OutputDir)
if (-not ($outputPath.StartsWith($rootPath) -or $outputPath.StartsWith([System.IO.Path]::GetTempPath()))) {
    throw "OutputDir must be inside the project or temp directory: $outputPath"
}

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$packageBaseName = "$Name-$Version"
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("$packageBaseName-staging-" + [System.Guid]::NewGuid().ToString("n"))
$zipPath = Join-Path $outputPath "$packageBaseName.zip"
$manifestPath = Join-Path $outputPath "$packageBaseName-manifest.json"

if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

$files = Get-PackageFiles $rootPath | Sort-Object FullName

foreach ($file in $files) {
    $relative = Get-RelativePath $file.FullName
    $target = Join-Path $stagingRoot $relative
    $targetDir = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target -Force
}

$manifestFiles = $files | ForEach-Object {
    $relative = (Get-RelativePath $_.FullName).Replace("\", "/")
    [pscustomobject]@{
        path = $relative
        size = $_.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    }
}

$blockedPackagePrefixes = @(".git/", ".omx/", ".venv/", "outputs/", "artifacts/tmp/", "artifacts/releases/")
$blockedPackageFiles = @(
    $manifestFiles |
        Where-Object {
            $filePath = $_.path
            foreach ($prefix in $blockedPackagePrefixes) {
                if ($filePath.StartsWith($prefix)) {
                    return $true
                }
            }
            return $false
        } |
        Select-Object -ExpandProperty path
)
if ($blockedPackageFiles.Count -gt 0) {
    throw "Package manifest contains excluded local artifacts: $($blockedPackageFiles -join ', ')"
}

$manifest = [pscustomobject]@{
    name = $Name
    version = $Version
    generated_at = (Get-Date).ToString("s")
    source_root = $rootPath
    package = $zipPath
    file_count = $manifestFiles.Count
    excluded = @(
        ".env",
        ".git/",
        ".omx/",
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        "pytest-cache-files-*/",
        "outputs/",
        "artifacts/tmp/",
        "artifacts/releases/",
        "*.db",
        "*.db-journal",
        "*.log",
        "*.pid",
        "*.pyc",
        "*.pyo"
    )
    files = $manifestFiles
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $zipPath -Force
Remove-Item -LiteralPath $stagingRoot -Recurse -Force

$result = [pscustomobject]@{
    ready = $true
    package = $zipPath
    manifest = $manifestPath
    file_count = $manifestFiles.Count
    size_bytes = (Get-Item -LiteralPath $zipPath).Length
}

$result | ConvertTo-Json -Depth 3
