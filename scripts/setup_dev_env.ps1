param(
    [string]$PythonCommand = "",
    [switch]$RunTests
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvDir = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

function Resolve-PythonCommand {
    if (-not [string]::IsNullOrWhiteSpace($PythonCommand)) {
        return @($PythonCommand)
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @("py", "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike "*WindowsApps*") {
        return @("python")
    }

    throw "No usable Python was found. Install Python 3.11+ or pass -PythonCommand with an explicit interpreter path."
}

function Invoke-Python {
    param([string[]]$Arguments)

    $command = Resolve-PythonCommand
    $exe = $command[0]
    $prefixArgs = @()
    if ($command.Count -gt 1) {
        $prefixArgs = $command[1..($command.Count - 1)]
    }
    & $exe @prefixArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$exe $($prefixArgs + $Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Invoke-VenvPython {
    param([string[]]$Arguments)

    & $venvPython @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$venvPython $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Invoke-Python @("-m", "venv", ".venv")
    }

    Invoke-VenvPython @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-VenvPython @("-m", "pip", "install", "-r", "requirements.txt")

    $result = [pscustomobject]@{
        ready = $true
        python = $venvPython
        run_tests = [bool]$RunTests
    }

    if ($RunTests) {
        Invoke-VenvPython @("-m", "pytest")
        $result | Add-Member -NotePropertyName tests -NotePropertyValue "passed"
    }

    $result | ConvertTo-Json -Depth 3
}
finally {
    Pop-Location
}
