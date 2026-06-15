param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$SkipRuntime
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$failures = New-Object System.Collections.Generic.List[string]
$checks = New-Object System.Collections.Generic.List[object]

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
    if (-not $Ok) {
        $failures.Add("${Name}: $Detail") | Out-Null
    }
}

function Test-ProjectPath {
    param([string]$Path)

    return Test-Path -LiteralPath (Join-Path $projectRoot $Path)
}

function Join-Url {
    param([string]$Root, [string]$Path)
    return $Root.TrimEnd("/") + "/" + $Path.TrimStart("/")
}

function Get-ReadmeReleaseUrl {
    param(
        [string]$Text,
        [string]$Label
    )

    $match = [regex]::Match($Text, "(?m)^$([regex]::Escape($Label))：(?<url>https://\S+)\s*$")
    if (-not $match.Success) {
        return $null
    }

    $url = $match.Groups["url"].Value.Trim().TrimEnd("/")
    if ($url -match "your-app\.example\.com|your-video\.example\.com") {
        return $null
    }

    return $url
}

function Get-ReleaseResidues {
    $residues = New-Object System.Collections.Generic.List[string]
    $skippedPrefixes = @(
        ".git",
        ".venv",
        "artifacts\tmp",
        "artifacts\releases"
    )

    Get-ChildItem -Path $projectRoot -Force -Recurse -ErrorAction SilentlyContinue |
        ForEach-Object {
            $relative = [System.IO.Path]::GetRelativePath($projectRoot, $_.FullName)
            foreach ($prefix in $skippedPrefixes) {
                if ($relative -eq $prefix -or $relative.StartsWith($prefix + [System.IO.Path]::DirectorySeparatorChar)) {
                    return
                }
            }

            if ($_.PSIsContainer) {
                if ($_.Name -eq "__pycache__" -or $_.Name -eq ".pytest_cache" -or $_.Name -like "pytest-cache-files-*") {
                    $residues.Add($relative) | Out-Null
                }
                return
            }

            if ($_.Name -eq ".env" -or
                $_.Name.EndsWith(".db") -or
                $_.Name.EndsWith(".db-journal") -or
                $_.Name.EndsWith(".log") -or
                $_.Name.EndsWith(".pid") -or
                $_.Name.EndsWith(".pyc") -or
                $_.Name.EndsWith(".pyo")) {
                $residues.Add($relative) | Out-Null
            }
        }

    return $residues | Sort-Object
}

function Get-ReleaseUrlPlaceholders {
    param([string[]]$Paths)

    $placeholders = New-Object System.Collections.Generic.List[string]
    foreach ($path in $Paths) {
        $fullPath = Join-Path $projectRoot $path
        if (-not (Test-Path -LiteralPath $fullPath)) {
            continue
        }

        $text = Get-Content -LiteralPath $fullPath -Raw
        $matches = [regex]::Matches($text, "your-app\.example\.com|your-video\.example\.com")
        foreach ($match in $matches) {
            $placeholders.Add("${path}:$($match.Value)") | Out-Null
        }
    }

    return $placeholders | Sort-Object -Unique
}

$requiredFiles = @(
    "AGENTS.md",
    "SECURITY.md",
    "README.md",
    "requirements.txt",
    "pyproject.toml",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "Procfile",
    "render.yaml",
    "railway.json",
    "fly.toml",
    ".github/workflows/ci.yml",
    "alembic.ini",
    "docs/PORTFOLIO_BRIEF.md",
    "docs/COMPLETION_AUDIT.md",
    "docs/API.md",
    "docs/ARCHITECTURE.md",
    "docs/DECISIONS.md",
    "docs/DEPLOYMENT.md",
    "docs/DEMO_SCRIPT.md",
    "docs/INTERVIEW_QA.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/PUBLIC_DELIVERY.md",
    "docs/VIDEO_RECORDING_GUIDE.md",
    "docs/HANDOFF_CHECKLIST.md",
    "scripts/final_acceptance.ps1",
    "scripts/smoke_check.ps1",
    "scripts/ui_text_audit.ps1",
    "scripts/deploy_config_audit.ps1",
    "scripts/evaluate_demo_fixtures.ps1",
    "scripts/verify_online_release.ps1",
    "scripts/package_release.ps1",
    "scripts/setup_dev_env.ps1",
    "scripts/update_release_links.ps1",
    "scripts/public_delivery_audit.ps1",
    "scripts/delivery_status.ps1",
    "scripts/test_delivery_status_contract.ps1",
    "scripts/generate_demo_exports.ps1",
    "scripts/clean_release_artifacts.ps1",
    "artifacts/samples/changeops-demo-delivery.md",
    "artifacts/samples/changeops-demo-delivery.pdf"
)

foreach ($file in $requiredFiles) {
    Add-Check "required:$file" (Test-ProjectPath $file) "required delivery file"
}

$releaseResidues = @(Get-ReleaseResidues)
Add-Check "release:clean-workspace" ($releaseResidues.Count -eq 0) ("release workspace should not contain runtime artifacts: " + ($releaseResidues -join ", "))

$sampleMarkdown = Join-Path $projectRoot "artifacts/samples/changeops-demo-delivery.md"
if (Test-Path -LiteralPath $sampleMarkdown) {
    $sampleText = Get-Content -LiteralPath $sampleMarkdown -Raw
    Add-Check "sample:markdown-title" ($sampleText.Contains("DBA ChangeOps AI 变更交付包")) "sample markdown should contain delivery title"
    Add-Check "sample:markdown-signoff" ($sampleText.Contains("签收状态：已签收")) "sample markdown should be a signed delivery package"
}

$samplePdf = Join-Path $projectRoot "artifacts/samples/changeops-demo-delivery.pdf"
if (Test-Path -LiteralPath $samplePdf) {
    $bytes = [System.IO.File]::ReadAllBytes($samplePdf)
    $header = if ($bytes.Length -ge 4) { [System.Text.Encoding]::ASCII.GetString($bytes, 0, 4) } else { "" }
    Add-Check "sample:pdf-header" ($header -eq "%PDF") "sample PDF should start with %PDF"
    Add-Check "sample:pdf-size" ($bytes.Length -gt 1024) "sample PDF should not be empty"
}

$readme = Join-Path $projectRoot "README.md"
if (Test-Path -LiteralPath $readme) {
    $readmeText = Get-Content -LiteralPath $readme -Raw
    $readmeDemoUrl = Get-ReadmeReleaseUrl $readmeText "在线演示"
    Add-Check "readme:online-demo-url" (-not [string]::IsNullOrWhiteSpace($readmeDemoUrl)) "README should include a real HTTPS online demo URL, not a placeholder"
    Add-Check "readme:api-doc" ($readmeText.Contains("docs/API.md")) "README should link API docs"
    Add-Check "readme:release-checklist" ($readmeText.Contains("docs/RELEASE_CHECKLIST.md")) "README should link release checklist"
}

$releaseUrlDocs = @(
    "README.md",
    "docs/COMPLETION_AUDIT.md",
    "docs/HANDOFF_CHECKLIST.md",
    "docs/PUBLIC_DELIVERY.md",
    "docs/RELEASE_CHECKLIST.md"
)
$releaseUrlPlaceholders = @(Get-ReleaseUrlPlaceholders $releaseUrlDocs)
Add-Check "docs:release-url-placeholders" ($releaseUrlPlaceholders.Count -eq 0) ("public delivery docs should use the verified DemoUrl and explicit VideoUrl input: " + ($releaseUrlPlaceholders -join ", "))

$packageScript = Join-Path $PSScriptRoot "package_release.ps1"
$packageTemp = Join-Path ([System.IO.Path]::GetTempPath()) ("changeops-readiness-package-" + [System.Guid]::NewGuid().ToString("n"))
try {
    if (Test-Path -LiteralPath $packageTemp) {
        Remove-Item -LiteralPath $packageTemp -Recurse -Force
    }
    if (Test-Path -LiteralPath $packageScript) {
        try {
            & $packageScript -OutputDir $packageTemp -Version "readiness-check" | Out-Null
            $manifestPath = Join-Path $packageTemp "dba-changeops-ai-workbench-readiness-check-manifest.json"
            $packagePath = Join-Path $packageTemp "dba-changeops-ai-workbench-readiness-check.zip"

            Add-Check "package:build" (Test-Path -LiteralPath $packagePath) "release package should be buildable"
            Add-Check "package:manifest" (Test-Path -LiteralPath $manifestPath) "release package manifest should be generated"

            if (Test-Path -LiteralPath $manifestPath) {
                $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
                $blockedPrefixes = @(".git/", ".omx/", ".venv/", "outputs/", "artifacts/tmp/", "artifacts/releases/")
                $blockedFiles = @(
                    $manifest.files |
                        Where-Object {
                            $filePath = $_.path
                            foreach ($prefix in $blockedPrefixes) {
                                if ($filePath.StartsWith($prefix)) {
                                    return $true
                                }
                            }
                            return $false
                        } |
                        Select-Object -ExpandProperty path
                )
                Add-Check "package:manifest-clean" ($blockedFiles.Count -eq 0) ("package manifest should exclude local artifacts: " + ($blockedFiles -join ", "))
                $packagedPaths = @($manifest.files | Select-Object -ExpandProperty path)
                Add-Check "package:manifest-agents" ($packagedPaths -contains "AGENTS.md") "package manifest should include project agent boundary"
                Add-Check "package:manifest-security" ($packagedPaths -contains "SECURITY.md") "package manifest should include security policy"
                Add-Check "package:file-count" ([int]$manifest.file_count -gt 0) "release package should contain delivery files"
            }
        }
        catch {
            Add-Check "package:build" $false $_.Exception.Message
        }
    }
    else {
        Add-Check "package:build" $false "Missing package script: $packageScript"
    }
}
finally {
    if (Test-Path -LiteralPath $packageTemp) {
        Remove-Item -LiteralPath $packageTemp -Recurse -Force
    }
}

if (-not $SkipRuntime) {
    try {
        $health = Invoke-RestMethod -Uri (Join-Url $BaseUrl "/healthz")
        Add-Check "runtime:healthz" ($health.status -eq "ok" -and $health.database -eq "ok") "healthz should report ok"
    }
    catch {
        Add-Check "runtime:healthz" $false $_.Exception.Message
    }

    try {
        $status = Invoke-RestMethod -Uri (Join-Url $BaseUrl "/api/system/status")
        Add-Check "runtime:system-status" ($status.database_ok -and $status.summary.total_cases -ge 5) "system status should have database and demo cases"
    }
    catch {
        Add-Check "runtime:system-status" $false $_.Exception.Message
    }
}

$result = [pscustomobject]@{
    ready = $failures.Count -eq 0
    base_url = if ($SkipRuntime) { $null } else { $BaseUrl }
    checked_at = (Get-Date).ToString("s")
    checks = $checks
    failures = $failures
}

$result | ConvertTo-Json -Depth 5

if ($failures.Count -gt 0) {
    exit 1
}
