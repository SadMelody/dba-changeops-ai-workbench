param(
    [Parameter(Mandatory = $true)]
    [string]$DemoUrl,
    [string]$VideoUrl,
    [string]$ReadmePath = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "README.md"),
    [switch]$AllowHttp
)

$ErrorActionPreference = "Stop"

function Normalize-Url {
    param(
        [string]$Name,
        [string]$Value,
        [bool]$Required
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        if ($Required) {
            throw "$Name cannot be empty"
        }
        return $null
    }

    $url = $Value.Trim().TrimEnd("/")
    if (-not ($url.StartsWith("https://") -or $url.StartsWith("http://"))) {
        throw "$Name must start with http:// or https://"
    }

    if ($url.StartsWith("http://") -and -not $AllowHttp) {
        $isLocal = $url.StartsWith("http://127.0.0.1") -or $url.StartsWith("http://localhost")
        if (-not $isLocal) {
            throw "$Name should use https://. Pass -AllowHttp only for a controlled internal target."
        }
    }

    return $url
}

$demo = Normalize-Url "DemoUrl" $DemoUrl $true
$video = Normalize-Url "VideoUrl" $VideoUrl $false

if (-not (Test-Path -LiteralPath $ReadmePath)) {
    throw "README not found: $ReadmePath"
}

$readme = Get-Content -LiteralPath $ReadmePath -Raw

$videoLine = if ($video) {
    "- [3-5 分钟备用演示视频]($video)"
}
else {
    "- [备用演示视频录制指南](docs/VIDEO_RECORDING_GUIDE.md)"
}

$releaseBlock = @"
在线演示：$demo

备用材料：

- [Markdown 样例交付包](artifacts/samples/changeops-demo-delivery.md)
- [PDF 样例交付包](artifacts/samples/changeops-demo-delivery.pdf)
- [3-5 分钟演示脚本](docs/DEMO_SCRIPT.md)
$videoLine
"@

$pattern = '(?s)在线演示：.*?备用材料：\r?\n\r?\n(?:- .+?\r?\n)+'
if (-not [regex]::IsMatch($readme, $pattern)) {
    throw "README release block was not found"
}

$updated = [regex]::Replace($readme, $pattern, $releaseBlock + [Environment]::NewLine, 1)
Set-Content -LiteralPath $ReadmePath -Value $updated -Encoding UTF8

$result = [pscustomobject]@{
    ready = $true
    readme = (Resolve-Path $ReadmePath).Path
    demo_url = $demo
    video_url = $video
    updated_at = (Get-Date).ToString("s")
}

$result | ConvertTo-Json -Depth 3
