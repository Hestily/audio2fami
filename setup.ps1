#Requires -Version 5.1
<#
.SYNOPSIS
  Native Windows setup for audio2fami (Python 3.11, ffmpeg, .NET 8, FamiStudio).
.PARAMETER Stems
  Also install Demucs + CPU PyTorch (large download).
#>
param(
    [switch]$Stems,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if ($Help) {
    Write-Host "Usage: .\setup.ps1 [-Stems]"
    Write-Host "  -Stems   also install Demucs + CPU PyTorch"
    exit 0
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$FamiVersion = "4.5.2"
$FamiZipUrl = "https://github.com/BleuBleu/FamiStudio/releases/download/$FamiVersion/FamiStudio452-WinPortableExe.zip"
$FfmpegZipUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$PythonInstallerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Test-Cmd($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Unblock-Tree($dir) {
    if (-not (Test-Path $dir)) { return }
    Get-ChildItem -LiteralPath $dir -Recurse -Include *.exe,*.dll,*.zip -ErrorAction SilentlyContinue |
        ForEach-Object { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue }
}

function Get-Python311 {
    foreach ($c in @("py", "python3.11", "python", "python3")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            if ($c -eq "py") {
                $ver = & py -3.11 -c "import sys; print('%d.%d'%sys.version_info[:2])" 2>$null
                if ($ver -match '^3\.(9|10|11)$') { return @("py", "-3.11") }
            } else {
                $ver = & $cmd.Source -c "import sys; print('%d.%d'%sys.version_info[:2])" 2>$null
                if ($ver -match '^3\.(9|10|11)$') { return @($cmd.Source) }
            }
        } catch { }
    }
    return $null
}

function Install-Uv {
    if (Test-Cmd "uv") { return }
    $uvDir = Join-Path $env:USERPROFILE ".local\bin"
    Write-Step "安装 uv（用于拿 Python 3.11 和装依赖）"
    try {
        irm https://astral.sh/uv/install.ps1 | iex
    } catch {
        Write-Host "uv 安装脚本失败，将改用 python.org 安装包。" -ForegroundColor Yellow
    }
    $env:Path = "$uvDir;$env:Path"
}

function Install-Python311 {
    $py = Get-Python311
    if ($py) { return $py }

    Install-Uv
    if (Test-Cmd "uv") {
        Write-Step "uv python install 3.11"
        & uv python install 3.11
        # uv will be used later to create venv; return a marker
        return @("uv-python")
    }

    if (Test-Cmd "winget") {
        Write-Step "winget install Python.Python.3.11"
        winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements --disable-interactivity
        $env:Path = "$env:LocalAppData\Programs\Python\Python311;$env:LocalAppData\Programs\Python\Python311\Scripts;$env:Path"
        $py = Get-Python311
        if ($py) { return $py }
    }

    Write-Step "下载 python.org 3.11.9 安装包（当前用户，加 PATH）"
    $inst = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $inst -UseBasicParsing
    Unblock-File $inst -ErrorAction SilentlyContinue
    & $inst /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
    $env:Path = "$env:LocalAppData\Programs\Python\Python311;$env:LocalAppData\Programs\Python\Python311\Scripts;$env:Path"
    $py = Get-Python311
    if (-not $py) { throw "安装 Python 3.11 失败。请从 https://www.python.org/downloads/ 手动安装 3.11，并勾选 Add python.exe to PATH。" }
    return $py
}

function Install-Dotnet8 {
    $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
    $has8 = $false
    if ($dotnet) {
        $runtimes = & dotnet --list-runtimes 2>$null
        if ($runtimes -match "Microsoft.NETCore.App 8\.") { $has8 = $true }
    }
    if ($has8) { return }

    Write-Step "安装 .NET 8 运行时（FamiStudio 便携版需要，不是自包含）"
    $script = Join-Path $env:TEMP "dotnet-install.ps1"
    Invoke-WebRequest -Uri "https://dot.net/v1/dotnet-install.ps1" -OutFile $script -UseBasicParsing
    & powershell -NoProfile -ExecutionPolicy Bypass -File $script -Channel 8.0 -Runtime dotnet -InstallDir "$env:USERPROFILE\.dotnet"
    $env:DOTNET_ROOT = "$env:USERPROFILE\.dotnet"
    $env:Path = "$env:USERPROFILE\.dotnet;$env:Path"
}

function Install-Ffmpeg {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Host "    已有 PATH 上的 ffmpeg"
        return
    }
    $dest = Join-Path $Root "third_party\ffmpeg"
    $exe = Join-Path $dest "ffmpeg.exe"
    if (Test-Path $exe) {
        Write-Host "    已有 $exe"
        $env:Path = "$dest;$env:Path"
        return
    }
    Write-Step "下载便携 ffmpeg 到 third_party\ffmpeg"
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "third_party") | Out-Null
    $zip = Join-Path $env:TEMP "ffmpeg-essentials.zip"
    Invoke-WebRequest -Uri $FfmpegZipUrl -OutFile $zip -UseBasicParsing
    $extract = Join-Path $env:TEMP "ffmpeg-extract"
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    Expand-Archive -LiteralPath $zip -DestinationPath $extract -Force
    $found = Get-ChildItem -LiteralPath $extract -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    if (-not $found) { throw "ffmpeg zip 里没有 ffmpeg.exe" }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $found.DirectoryName "*") -Destination $dest -Force
    Unblock-Tree $dest
    $env:Path = "$dest;$env:Path"
}

function Install-FamiStudio {
    $dest = Join-Path $Root "third_party\FamiStudio"
    $exe = Join-Path $dest "FamiStudio.exe"
    $dll = Join-Path $dest "FamiStudio.dll"
    if ((Test-Path $exe) -or (Test-Path $dll)) {
        Write-Host "    已有 FamiStudio"
        Unblock-Tree $dest
        return
    }
    Write-Step "下载 FamiStudio $FamiVersion Windows 便携版"
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "third_party") | Out-Null
    $zip = Join-Path $env:TEMP "FamiStudio-win.zip"
    Invoke-WebRequest -Uri $FamiZipUrl -OutFile $zip -UseBasicParsing
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Expand-Archive -LiteralPath $zip -DestinationPath $dest -Force
    if (-not ((Test-Path $exe) -or (Test-Path $dll))) {
        $inner = Get-ChildItem $dest -Directory | Select-Object -First 1
        if ($inner) {
            Get-ChildItem -LiteralPath $inner.FullName | Move-Item -Destination $dest -Force
        }
    }
    Unblock-Tree $dest
    if (-not ((Test-Path $exe) -or (Test-Path $dll))) {
        throw "解压后找不到 FamiStudio.exe / FamiStudio.dll"
    }
}

Write-Step "检查 / 安装 Python 3.9–3.11（basic-pitch / TensorFlow 不支持 3.12+）"
$Py = Install-Python311
if ($Py -and $Py[0] -ne "uv-python") {
    Write-Host ("    使用 " + ($Py -join " "))
}

Write-Step "创建 venv 并安装 pinned 依赖"
$venv = Join-Path $Root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (Test-Cmd "uv") {
    & uv venv -p 3.11 $venv
    & uv pip install --python $venvPy "setuptools==80.9.0" "numpy==1.26.4"
    & uv pip install --python $venvPy -r (Join-Path $Root "requirements.txt")
    & uv pip install --python $venvPy -e $Root
} else {
    if ($Py[0] -eq "uv-python") { throw "需要 Python 3.11 或 uv" }
    $pyArgs = @()
    if ($Py.Count -gt 1) { $pyArgs = $Py[1..($Py.Count-1)] }
    & $Py[0] @pyArgs -m venv $venv
    & $venvPy -m pip install -U pip "setuptools==80.9.0" wheel
    & $venvPy -m pip install "numpy==1.26.4"
    & $venvPy -m pip install -r (Join-Path $Root "requirements.txt")
    & $venvPy -m pip install -e $Root
}

Install-Ffmpeg
Install-Dotnet8
Install-FamiStudio

if ($Stems) {
    Write-Step "安装 Demucs + CPU PyTorch"
    if (Test-Cmd "uv") {
        & uv pip install --python $venvPy --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match -r (Join-Path $Root "requirements-stems.txt")
    } else {
        & $venvPy -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r (Join-Path $Root "requirements-stems.txt")
    }
}

# Persist user PATH pieces for later cmd.exe sessions
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$extra = @()
$ffmpegDir = Join-Path $Root "third_party\ffmpeg"
$dotnetDir = Join-Path $env:USERPROFILE ".dotnet"
if (Test-Path (Join-Path $ffmpegDir "ffmpeg.exe")) { $extra += $ffmpegDir }
if (Test-Path (Join-Path $dotnetDir "dotnet.exe")) {
    $extra += $dotnetDir
    [Environment]::SetEnvironmentVariable("DOTNET_ROOT", $dotnetDir, "User")
}
foreach ($p in $extra) {
    if ($userPath -notlike "*$p*") {
        $userPath = "$p;$userPath"
        [Environment]::SetEnvironmentVariable("Path", $userPath, "User")
    }
}

Write-Host ""
Write-Host "安装完成。" -ForegroundColor Green
Write-Host "  audio2fami.cmd samples\gymnopedie_30s.wav -f mp3 -o artifacts\out.mp3 --duration 25"
Write-Host "  start-ui.cmd"
Write-Host ""
Write-Host "若 SmartScreen 拦截 FamiStudio：属性 → 解除锁定，或重新运行 setup.cmd。"
Write-Host "PowerShell 执行策略被拦时请用 setup.cmd，不要直接 .\setup.ps1。"
