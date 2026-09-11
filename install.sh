#!/bin/bash
#
# BeethovenFlow Installer for macOS
# Installs MPV, yt-dlp, and BeethovenFlow
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo -e "${CYAN}${BOLD}🎵 BeethovenFlow Installer${NC}"
echo -e "${CYAN}─────────────────────────────────${NC}"
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}Error: This script is for macOS only.${NC}"
    echo "For Windows, run install.ps1 in PowerShell."
    exit 1
fi

# Check for Homebrew
check_homebrew() {
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}Homebrew not found. Installing...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add Homebrew to PATH for Apple Silicon
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    else
        echo -e "${GREEN}✓ Homebrew found${NC}"
    fi
}

# Install MPV
install_mpv() {
    if command -v mpv &> /dev/null; then
        echo -e "${GREEN}✓ MPV already installed${NC}"
        mpv --version | head -1
    else
        echo -e "${YELLOW}Installing MPV...${NC}"
        brew install mpv
        echo -e "${GREEN}✓ MPV installed${NC}"
    fi
}

# Install yt-dlp
install_ytdlp() {
    if command -v yt-dlp &> /dev/null; then
        echo -e "${GREEN}✓ yt-dlp already installed${NC}"
        yt-dlp --version
    else
        echo -e "${YELLOW}Installing yt-dlp...${NC}"
        brew install yt-dlp
        echo -e "${GREEN}✓ yt-dlp installed${NC}"
    fi
}

# Install Python dependencies and BeethovenFlow
install_beethovenflow() {
    echo ""
    echo -e "${YELLOW}Installing BeethovenFlow...${NC}"
    
    # Check for Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Installing Python...${NC}"
        brew install python
    fi
    
    # Check for pip
    if ! python3 -m pip --version &> /dev/null; then
        echo -e "${YELLOW}Installing pip...${NC}"
        python3 -m ensurepip --upgrade
    fi
    
    # Install BeethovenFlow
    # If running from the repo directory, install in editable mode
    if [[ -f "pyproject.toml" ]]; then
        echo "Installing from local source..."
        python3 -m pip install -e . --quiet
    else
        # Try to install from PyPI (if published) or provide instructions
        echo "Installing dependencies..."
        python3 -m pip install pynput numpy yt-dlp --quiet
        echo ""
        echo -e "${YELLOW}Note: BeethovenFlow is not installed from PyPI.${NC}"
        echo "Please run this script from the BeethovenFlow source directory."
    fi
    
    echo -e "${GREEN}✓ BeethovenFlow installed${NC}"
}

# Setup accessibility permissions reminder
setup_permissions() {
    echo ""
    echo -e "${CYAN}${BOLD}⚠️  Important: Accessibility Permissions${NC}"
    echo ""
    echo "BeethovenFlow needs accessibility permissions to track mouse movement."
    echo ""
    echo "After running BeethovenFlow for the first time:"
    echo "1. Go to System Settings > Privacy & Security > Accessibility"
    echo "2. Enable your terminal app (Terminal, iTerm2, etc.)"
    echo ""
    echo -e "${YELLOW}Press any key to open System Settings...${NC}"
    read -n 1 -s
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
}

# Create launch script
create_launcher() {
    LAUNCHER="$HOME/Desktop/BeethovenFlow.command"
    
    echo "#!/bin/bash" > "$LAUNCHER"
    echo "cd ~" >> "$LAUNCHER"
    echo "beethovenflow" >> "$LAUNCHER"
    chmod +x "$LAUNCHER"
    
    echo ""
    echo -e "${GREEN}✓ Created desktop launcher: BeethovenFlow.command${NC}"
}

# Main installation flow
main() {
    check_homebrew
    echo ""
    
    install_mpv
    install_ytdlp
    install_beethovenflow
    
    echo ""
    echo -e "${GREEN}${BOLD}✓ Installation complete!${NC}"
    echo ""
    
    # Ask about desktop launcher
    echo -e "Create desktop launcher? [Y/n] "
    read -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        create_launcher
    fi
    
    # Remind about permissions
    setup_permissions
    
    echo ""
    echo -e "${CYAN}${BOLD}To start BeethovenFlow:${NC}"
    echo "  beethovenflow"
    echo ""
    echo "Or double-click BeethovenFlow.command on your desktop."
    echo ""
}

main
