#
# BeethovenFlow Installer for Windows
# Installs MPV, yt-dlp, and BeethovenFlow
#
# Run in PowerShell: .\install.ps1
#

$ErrorActionPreference = "Stop"

# Colors
function Write-Color {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

Write-Host ""
Write-Color "🎵 BeethovenFlow Installer" "Cyan"
Write-Color "─────────────────────────────────" "Cyan"
Write-Host ""

# Check for admin rights (not required, but helpful for chocolatey)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# Check for Chocolatey
function Install-Chocolatey {
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Color "✓ Chocolatey found" "Green"
        return $true
    }
    
    Write-Color "Chocolatey not found. Installing..." "Yellow"
    
    if (-not $isAdmin) {
        Write-Color "⚠ Installing Chocolatey requires admin rights." "Yellow"
        Write-Host "Please run PowerShell as Administrator and try again."
        Write-Host ""
        Write-Host "Or install dependencies manually:"
        Write-Host "  1. Download MPV: https://mpv.io/installation/"
        Write-Host "  2. Download yt-dlp: https://github.com/yt-dlp/yt-dlp/releases"
        Write-Host "  3. Add both to your PATH"
        return $false
    }
    
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    
    # Refresh environment
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    Write-Color "✓ Chocolatey installed" "Green"
    return $true
}

# Check for winget (Windows 11 / Windows 10 with App Installer)
function Test-Winget {
    return Get-Command winget -ErrorAction SilentlyContinue
}

# Install MPV
function Install-MPV {
    if (Get-Command mpv -ErrorAction SilentlyContinue) {
        Write-Color "✓ MPV already installed" "Green"
        & mpv --version | Select-Object -First 1
        return
    }
    
    Write-Color "Installing MPV..." "Yellow"
    
    if (Test-Winget) {
        winget install mpv --silent --accept-package-agreements --accept-source-agreements
    }
    elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install mpv -y
    }
    else {
        Write-Color "Please install MPV manually from: https://mpv.io/installation/" "Red"
        return
    }
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    Write-Color "✓ MPV installed" "Green"
}

# Install yt-dlp
function Install-YtDlp {
    if (Get-Command yt-dlp -ErrorAction SilentlyContinue) {
        Write-Color "✓ yt-dlp already installed" "Green"
        & yt-dlp --version
        return
    }
    
    Write-Color "Installing yt-dlp..." "Yellow"
    
    if (Test-Winget) {
        winget install yt-dlp --silent --accept-package-agreements --accept-source-agreements
    }
    elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install yt-dlp -y
    }
    else {
        # Manual installation to user's local bin
        $installDir = "$env:LOCALAPPDATA\Programs\yt-dlp"
        New-Item -ItemType Directory -Force -Path $installDir | Out-Null
        
        Write-Host "Downloading yt-dlp..."
        $url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        Invoke-WebRequest -Uri $url -OutFile "$installDir\yt-dlp.exe"
        
        # Add to user PATH
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -notlike "*$installDir*") {
            [Environment]::SetEnvironmentVariable("Path", "$userPath;$installDir", "User")
            $env:Path = "$env:Path;$installDir"
        }
    }
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    Write-Color "✓ yt-dlp installed" "Green"
}

# Install Python (if needed) and BeethovenFlow
function Install-BeethovenFlow {
    Write-Host ""
    Write-Color "Installing BeethovenFlow..." "Yellow"
    
    # Check for Python
    $pythonCmd = $null
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCmd = "python"
    }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        $pythonCmd = "python3"
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCmd = "py"
    }
    
    if (-not $pythonCmd) {
        Write-Color "Python not found. Installing..." "Yellow"
        
        if (Test-Winget) {
            winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
        }
        elseif (Get-Command choco -ErrorAction SilentlyContinue) {
            choco install python -y
        }
        else {
            Write-Color "Please install Python from: https://www.python.org/downloads/" "Red"
            return
        }
        
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $pythonCmd = "python"
    }
    
    Write-Color "✓ Python found: $pythonCmd" "Green"
    
    # Install BeethovenFlow
    if (Test-Path "pyproject.toml") {
        Write-Host "Installing from local source..."
        & $pythonCmd -m pip install -e . --quiet
    }
    else {
        Write-Host "Installing dependencies..."
        & $pythonCmd -m pip install pynput numpy yt-dlp --quiet
        Write-Host ""
        Write-Color "Note: BeethovenFlow is not installed from PyPI." "Yellow"
        Write-Host "Please run this script from the BeethovenFlow source directory."
    }
    
    Write-Color "✓ BeethovenFlow installed" "Green"
}

# Create desktop shortcut
function New-DesktopShortcut {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = "$desktop\BeethovenFlow.bat"
    
    @"
@echo off
title BeethovenFlow
beethovenflow
pause
"@ | Out-File -FilePath $shortcutPath -Encoding ASCII
    
    Write-Host ""
    Write-Color "✓ Created desktop shortcut: BeethovenFlow.bat" "Green"
}

# Main installation
function Main {
    # Try to use winget first, fall back to chocolatey
    if (-not (Test-Winget)) {
        $chocoInstalled = Install-Chocolatey
        if (-not $chocoInstalled -and -not $isAdmin) {
            Write-Host ""
            Write-Host "You can still install BeethovenFlow manually:"
            Write-Host "  1. Install Python: https://www.python.org/downloads/"
            Write-Host "  2. Install MPV: https://mpv.io/installation/"
            Write-Host "  3. Install yt-dlp: https://github.com/yt-dlp/yt-dlp/releases"
            Write-Host "  4. Run: pip install pynput numpy yt-dlp"
            Write-Host "  5. Run: pip install -e . (from BeethovenFlow directory)"
            return
        }
    }
    else {
        Write-Color "✓ winget found (will use for installations)" "Green"
    }
    
    Write-Host ""
    
    Install-MPV
    Install-YtDlp
    Install-BeethovenFlow
    
    Write-Host ""
    Write-Color "✓ Installation complete!" "Green"
    Write-Host ""
    
    # Ask about desktop shortcut
    $createShortcut = Read-Host "Create desktop shortcut? [Y/n]"
    if ($createShortcut -ne "n" -and $createShortcut -ne "N") {
        New-DesktopShortcut
    }
    
    Write-Host ""
    Write-Color "To start BeethovenFlow:" "Cyan"
    Write-Host "  beethovenflow"
    Write-Host ""
    Write-Host "Or double-click BeethovenFlow.bat on your desktop."
    Write-Host ""
}

Main
