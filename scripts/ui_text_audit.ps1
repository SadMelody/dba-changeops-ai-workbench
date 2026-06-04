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
    $checks.Add($check)
    if (-not $Ok) {
        $failures.Add($check)
    }
}

function Read-ProjectText {
    param([string]$Path)

    $fullPath = Join-Path $Root $Path
    if (-not (Test-Path -LiteralPath $fullPath)) {
        Add-Check "file:$Path" $false "required UI file is missing"
        return ""
    }

    Add-Check "file:$Path" $true "required UI file exists"
    return Get-Content -LiteralPath $fullPath -Raw
}

function Assert-Contains {
    param(
        [string]$Name,
        [string]$Text,
        [string]$Needle,
        [string]$Detail
    )

    Add-Check $Name ($Text.Contains($Needle)) $Detail
}

$baseText = Read-ProjectText "app/templates/base.html"
$homeText = Read-ProjectText "app/templates/home.html"
$demoText = Read-ProjectText "app/templates/demo.html"
$newCaseText = Read-ProjectText "app/templates/new_case.html"
$caseDetailText = Read-ProjectText "app/templates/case_detail.html"
$runDetailText = Read-ProjectText "app/templates/run_detail.html"
$operationsText = Read-ProjectText "app/templates/operations.html"
$readmeText = Read-ProjectText "README.md"

Assert-Contains "ui:html-lang" $baseText '<html lang="zh-CN">' "base template should declare Chinese locale"
Assert-Contains "ui:brand-subtitle" $baseText "AI 变更交付工作台" "sidebar brand should use Chinese product positioning"
Assert-Contains "ui:nav-cases" $baseText "案例" "navigation should expose cases in Chinese"
Assert-Contains "ui:nav-demo" $baseText "交付演示" "navigation should expose demo in Chinese"
Assert-Contains "ui:nav-ops" $baseText "运行状态" "navigation should expose ops in Chinese"
Assert-Contains "ui:new-case-action" $baseText "新建案例" "primary creation action should be Chinese"

Assert-Contains "ui:home-readiness" $homeText "交付就绪度" "home page should show delivery readiness in Chinese"
Assert-Contains "ui:home-case-list" $homeText "变更案例" "home page should label change cases in Chinese"
Assert-Contains "ui:home-generate" $homeText "生成交付方案" "home page should expose generation action in Chinese"

Assert-Contains "ui:demo-generate" $demoText "一键生成交付包" "demo page should expose one-click generation in Chinese"
Assert-Contains "ui:demo-complete" $demoText "一键完整闭环" "demo page should expose full demo closure in Chinese"
Assert-Contains "ui:demo-export" $demoText "导出 PDF" "demo page should expose PDF export in Chinese"

Assert-Contains "ui:new-form-title" $newCaseText "新建数据库变更案例" "new case page should be Chinese"
Assert-Contains "ui:new-form-save" $newCaseText "保存案例" "new case save action should be Chinese"

Assert-Contains "ui:case-detail-title" $caseDetailText "变更案例详情" "case detail page should be Chinese"
Assert-Contains "ui:case-detail-export" $caseDetailText "导出 Markdown" "case detail export action should be Chinese"

Assert-Contains "ui:run-title" $runDetailText "AI 变更交付包" "run detail page should be Chinese"
Assert-Contains "ui:run-readiness" $runDetailText "交付完成度" "run detail page should show delivery completion in Chinese"
Assert-Contains "ui:run-signoff" $runDetailText "签收交付包" "run detail page should expose signoff in Chinese"
Assert-Contains "ui:run-audit" $runDetailText "LLM 调用审计" "run detail page should show LLM audit in Chinese"

Assert-Contains "ui:ops-title" $operationsText "运行状态" "ops page should be Chinese"
Assert-Contains "ui:ops-check" $operationsText "交付核验" "ops page should expose delivery checks in Chinese"

Assert-Contains "readme:screenshots" $readmeText "artifacts/screenshots/home.png" "README should link UI screenshots"
Assert-Contains "readme:portfolio" $readmeText "docs/PORTFOLIO_BRIEF.md" "README should link the one-page portfolio brief"

$screenshots = @(
    "artifacts/screenshots/home.png",
    "artifacts/screenshots/demo.png",
    "artifacts/screenshots/run-detail.png"
)

foreach ($screenshot in $screenshots) {
    $fullPath = Join-Path $Root $screenshot
    $exists = Test-Path -LiteralPath $fullPath
    Add-Check "screenshot:exists:$screenshot" $exists "screenshot should exist for interview evidence"
    if ($exists) {
        $size = (Get-Item -LiteralPath $fullPath).Length
        Add-Check "screenshot:size:$screenshot" ($size -gt 1024) "screenshot should not be empty"
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
