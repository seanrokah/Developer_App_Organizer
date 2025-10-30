#!/bin/bash
# Author: Sean Rokah
# Date: 2025-10-30
# Version: 1.3.1
# Description: Start the management server with Docker Compose

set -e

# Variables - declared at the beginning
BUILD=false
DOCKER_MODEL_AVAILABLE=false
LOCAL_IP="localhost"
ENABLE_LLM=false

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

Start the DevOps Organizer management server with Docker Compose

OPTIONS:
    --build          Rebuild Docker images before starting
    -h, --help       Show this help message

EXAMPLES:
    $0                    # Start server with existing images
    $0 --build            # Rebuild images and start server

EOF
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        msg error "Docker is required but not installed"
        return 1
    fi
    
    if ! docker compose version &> /dev/null; then
        msg error "Docker Compose is required but not available"
        return 1
    fi
    
    msg success "Docker and Docker Compose found"
    return 0
}

check_docker_model() {
    msg info "Checking for Docker Model availability..."
    
    # Check if docker model command is available
    if ! command -v docker model &> /dev/null; then
        msg warning "Docker Model command not found."
        echo
        echo -e "${YELLOW}🤖 AI Assistant features will be disabled.${NC}"
        echo
        echo "To enable AI Assistant features (optional):"
        echo "  1. Update Docker Desktop to the latest version that includes Docker Model support"
        echo "  2. Enable Docker Model in Docker Desktop settings"
        echo "  3. Restart the server with: ${BLUE}./start-server.sh${NC}"
        echo
        echo "For more information, visit: https://docs.docker.com/reference/cli/docker/model/"
        echo
        msg info "Continuing without AI features..."
        return 1
    fi
    
    # Check Docker Model Runner status
    local model_status
    model_status=$(docker model status 2>/dev/null || echo "")
    
    if [[ "$model_status" == *"Docker Model Runner is running"* ]]; then
        msg success "Docker Model Runner is running! AI Assistant features will be enabled."
        return 0
    else
        msg warning "Docker Model Runner is not running."
        echo
        echo -e "${YELLOW}🤖 AI Assistant features will be disabled.${NC}"
        echo
        if [ -n "$model_status" ]; then
            echo "Current status: $model_status"
            echo
        fi
        echo "To enable AI Assistant features (optional):"
        echo "  1. Start Docker Model Runner in Docker Desktop"
        echo "  2. Or run: docker model start (if available)"
        echo "  3. Restart the server with: ${BLUE}./start-server.sh${NC}"
        echo
        msg info "Continuing without AI features..."
        return 1
    fi
}

build_images() {
    msg info "Building Docker images..."
    
    local build_result=0
    if [ "$DOCKER_MODEL_AVAILABLE" = true ]; then
        # Build all services in llm profile
        docker compose --profile llm build || build_result=1
    else
        # Build only core services
        docker compose build devops-organizer nginx || build_result=1
    fi
    
    if [ $build_result -ne 0 ]; then
        msg error "Failed to build Docker images"
        return 1
    fi
    
    msg success "Images built successfully"
    return 0
}

get_local_ip() {
    # Try to get the local IP address
    if command -v ip &> /dev/null; then
        LOCAL_IP=$(ip route get 8.8.8.8 2>/dev/null | sed -n '/src/{s/.*src *\([^ ]*\).*/\1/p;q}' || echo "")
    elif command -v ifconfig &> /dev/null; then
        LOCAL_IP=$(ifconfig | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d':' -f2 || echo "")
    else
        LOCAL_IP="localhost"
    fi
    
    # Validate IP or default to localhost
    if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" = "127.0.0.1" ]; then
        LOCAL_IP="localhost"
    fi
}

start_services() {
    msg info "Starting DevOps Organizer management server..."
    
    local start_result=0
    if [ "$DOCKER_MODEL_AVAILABLE" = true ]; then
        msg info "Starting all services including AI Assistant..."
        docker compose --profile llm up -d || start_result=1
    else
        msg info "Starting core services (without AI Assistant)..."
        docker compose up -d devops-organizer nginx || start_result=1
    fi
    
    if [ $start_result -ne 0 ]; then
        msg error "Failed to start services"
        return 1
    fi
    
    # Wait a moment for services to start
    sleep 3
    
    msg success "Management server started successfully!"
    return 0
}

display_info() {
    if [ "$DOCKER_MODEL_AVAILABLE" = true ]; then
        msg success "🤖 AI Assistant is enabled and available in the dashboard!"
    else
        msg warning "🤖 AI Assistant is disabled (Docker Model not available)"
    fi
    
    echo
    echo -e "${BLUE}🌐 Access Information:${NC}"
    echo "  Web Dashboard: http://localhost:8085"
    echo "  Management API: http://localhost:8085"
    if [ "$LOCAL_IP" != "localhost" ]; then
        echo "  Network Access: http://$LOCAL_IP:8085"
        echo "  Network API: http://$LOCAL_IP:8085"
    fi
    echo
    echo -e "${BLUE}📱 Agent Installation:${NC}"
    echo "  On this machine:"
    echo "    cd agent/ && ./simple-install.sh"
    echo "    python3 ~/.devops-agent/simple-agent.py --server http://localhost:8085 --once"
    echo
    echo "  On remote machines:"
    echo "    ./simple-install.sh"
    if [ "$LOCAL_IP" != "localhost" ]; then
        echo "    python3 ~/.devops-agent/simple-agent.py --server http://$LOCAL_IP:8085"
    else
        echo "    python3 ~/.devops-agent/simple-agent.py --server http://[SERVER_IP]:8085"
    fi
    echo
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo "  View logs:     docker compose logs -f"
    echo "  Stop server:   docker compose down"
    echo "  Restart:       docker compose restart"
    echo
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Open http://localhost:8085 in your browser"
    echo "  2. Install agents on machines you want to monitor"
    echo "  3. Watch your infrastructure come to life!"
}

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --build)
                BUILD=true
                shift
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
    
    msg header "DevOps Developer Organizer"
    
    # Check Docker availability
    if ! check_docker; then
        exit 1
    fi
    
    # Get local IP address
    get_local_ip
    
    # Check for Docker Model availability
    if check_docker_model; then
        DOCKER_MODEL_AVAILABLE=true
        ENABLE_LLM=true
        export ENABLE_LLM
    else
        DOCKER_MODEL_AVAILABLE=false
        ENABLE_LLM=false
        export ENABLE_LLM
    fi
    
    # Optionally rebuild images
    if [ "$BUILD" = true ]; then
        if ! build_images; then
            exit 1
        fi
    fi
    
    # Start services
    if ! start_services; then
        exit 1
    fi
    
    # Display information
    display_info
}

main "$@"
