#!/bin/bash

# DevOps Organizer Simple Agent - Installation Script
# Just installs dependencies and copies files - no daemon setup

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Variables - declared at the beginning
INSTALL_DIR="$HOME/.devops-agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
AGENT_FILE="$SCRIPT_DIR/simple-agent.py"
INSTALL_SUCCESS=false

# Unified message function
msg() {
    local type=$1
    shift
    local message="$*"
    
    case $type in
        success)
            echo -e "${GREEN}✓ $message${NC}"
            ;;
        info)
            echo -e "${BLUE}ℹ $message${NC}"
            ;;
        warning)
            echo -e "${YELLOW}⚠ $message${NC}"
            ;;
        error)
            echo -e "${RED}✗ $message${NC}"
            ;;
        header)
            echo -e "${BLUE}================================================${NC}"
            echo -e "${BLUE}  $message${NC}"
            echo -e "${BLUE}================================================${NC}"
            ;;
    esac
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Simple setup for DevOps Organizer Agent

OPTIONS:
    --install-dir DIR   Installation directory (default: ~/.devops-agent)
    -h, --help          Show this help message

EXAMPLES:
    $0                                    # Install to default location
    $0 --install-dir /opt/devops-agent    # Install to custom location

EOF
}

check_requirements() {
    msg info "Checking requirements..."
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        msg error "Python 3 is required but not installed"
        return 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        msg error "pip3 is required but not installed"
        return 1
    fi
    
    python_version=$(python3 --version)
    msg success "Found $python_version"
    msg success "Requirements satisfied"
    return 0
}

install_dependencies() {
    msg info "Installing Python dependencies..."
    
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        msg error "requirements.txt not found in $SCRIPT_DIR"
        return 1
    fi
    
    # Check for virtual environment
    local venv_active=false
    if [[ -n "$VIRTUAL_ENV" ]]; then
        venv_active=true
        msg info "Virtual environment detected: $VIRTUAL_ENV"
    fi
    
    # Install dependencies
    local install_result=0
    if [ "$venv_active" = true ]; then
        pip3 install -r "$REQUIREMENTS_FILE" || install_result=1
    else
        msg info "Installing with --user flag"
        pip3 install --user -r "$REQUIREMENTS_FILE" || install_result=1
    fi
    
    if [ $install_result -ne 0 ]; then
        msg error "Failed to install dependencies"
        msg warning "Attempting forced installation..."
        pip3 install --user --force-reinstall -r "$REQUIREMENTS_FILE" || {
            msg error "Dependency installation failed completely"
            return 1
        }
    fi
    
    msg success "Dependencies installed"
    return 0
}

setup_agent() {
    msg info "Setting up agent files..."
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy agent files
    if [ ! -f "$AGENT_FILE" ]; then
        msg error "simple-agent.py not found"
        return 1
    fi
    
    cp "$AGENT_FILE" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/simple-agent.py"
    msg success "Copied simple-agent.py"
    
    if [ -f "$REQUIREMENTS_FILE" ]; then
        cp "$REQUIREMENTS_FILE" "$INSTALL_DIR/"
        msg success "Copied requirements.txt"
    fi
    
    msg success "Agent files set up in $INSTALL_DIR"
    return 0
}

show_usage_instructions() {
    msg success "Setup completed!"
    echo
    echo -e "${BLUE}Agent Location:${NC}"
    echo "  $INSTALL_DIR/simple-agent.py"
    echo
    echo -e "${BLUE}Usage Examples:${NC}"
    echo "  # Run once and exit"
    echo "  python3 $INSTALL_DIR/simple-agent.py --server http://192.168.1.100:8085 --once"
    echo
    echo "  # Run continuously (default 30s interval)"
    echo "  python3 $INSTALL_DIR/simple-agent.py --server http://192.168.1.100:8085"
    echo
    echo "  # Run with custom name and interval"
    echo "  python3 $INSTALL_DIR/simple-agent.py --server http://192.168.1.100:8085 --name \"my-laptop\" --interval 60"
    echo
    echo -e "${BLUE}Available Options:${NC}"
    echo "  --server URL     Management server URL (required)"
    echo "  --name NAME      Agent name (default: hostname)"
    echo "  --interval SEC   Report interval in seconds (default: 30)"
    echo "  --once           Run once and exit"
    echo
    echo -e "${YELLOW}Quick Start:${NC}"
    echo "  1. Start your management server"
    echo "  2. Run: python3 $INSTALL_DIR/simple-agent.py --server http://[SERVER]:8085 --once"
    echo "  3. Check the management UI to see your agent data"
    echo
    echo -e "${YELLOW}For Continuous Monitoring:${NC}"
    echo "  python3 $INSTALL_DIR/simple-agent.py --server http://[SERVER]:8085"
    echo "  (Press Ctrl+C to stop)"
}

prompt_run_now() {
    echo
    msg info "Configure continuous monitoring"
    read -r -p "Management server URL (e.g., http://192.168.1.100:8085): " SERVER_URL
    if [ -z "$SERVER_URL" ]; then
        msg warning "No server URL provided. Skipping run."
        return 0
    fi

    read -r -p "Agent name (optional, press Enter to use hostname): " AGENT_NAME
    read -r -p "Report interval seconds (optional, default 30): " INTERVAL

    CMD="python3 $INSTALL_DIR/simple-agent.py --server $SERVER_URL"
    if [ -n "$AGENT_NAME" ]; then
        CMD="$CMD --name \"$AGENT_NAME\""
    fi
    if [ -n "$INTERVAL" ]; then
        CMD="$CMD --interval $INTERVAL"
    fi

    echo
    echo -e "${BLUE}Command:${NC} $CMD"
    read -r -p "Run now continuously? (y/N): " RUN_NOW
    case "$RUN_NOW" in
        [yY]|[yY][eE][sS])
            echo
            msg info "Starting agent (press Ctrl+C to stop)..."
            eval "$CMD"
            ;;
        *)
            echo
            msg info "Not running now. Use this command when ready:"
            echo "$CMD"
            ;;
    esac
}

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                msg error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    msg header "DevOps Organizer Simple Agent Setup"
    
    # Check requirements and handle errors
    if ! check_requirements; then
        exit 1
    fi
    
    # Install dependencies and handle errors
    if ! install_dependencies; then
        msg error "Installation failed at dependency step"
        exit 1
    fi
    
    # Setup agent and handle errors
    if ! setup_agent; then
        msg error "Installation failed at setup step"
        exit 1
    fi
    
    # Show instructions
    show_usage_instructions
    
    # Prompt for running
    prompt_run_now
    
    INSTALL_SUCCESS=true
}

main "$@"
