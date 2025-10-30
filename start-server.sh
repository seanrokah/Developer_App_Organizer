#!/bin/bash
# Author: Sean Rokah
# Date: 2025-09-16
# Version: 1.0.0
# Description: Start the management server with Docker Compose

# DevOps Organizer - Quick Start Script
# Start the management server with Docker Compose

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  DevOps Developer Organizer${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

usage() {
	echo "Usage: $0 [--build]"
	echo "  --build    Rebuild Docker images before starting"
}

BUILD=false

# Parse arguments
for arg in "$@"; do
	case $arg in
		--build)
			BUILD=true
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			;;
	esac
done

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is required but not installed"
        exit 1
    fi
    
    print_success "Docker and Docker Compose found"
}

check_docker_model() {
    print_info "Checking for Docker Model availability..."
    
    # Check if docker model command is available
    if ! command -v docker model &> /dev/null; then
        print_warning "Docker Model command not found."
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
        print_info "Continuing without AI features..."
        return 1
    fi
    
    # Check Docker Model Runner status
    local model_status
    model_status=$(docker model status 2>/dev/null || echo "")
    
    if [[ "$model_status" == *"Docker Model Runner is running"* ]]; then
        print_success "Docker Model Runner is running! AI Assistant features will be enabled."
        return 0
    else
        print_warning "Docker Model Runner is not running."
        echo
        echo -e "${YELLOW}🤖 AI Assistant features will be disabled.${NC}"
        echo
        echo "Current status: $model_status"
        echo
        echo "To enable AI Assistant features (optional):"
        echo "  1. Start Docker Model Runner in Docker Desktop"
        echo "  2. Or run: docker model start (if available)"
        echo "  3. Restart the server with: ${BLUE}./start-server.sh${NC}"
        echo
        print_info "Continuing without AI features..."
        return 1
    fi
}

build_images() {
	print_info "Building Docker images..."
	if $DOCKER_MODEL_AVAILABLE; then
		# Build all services in llm profile
		docker compose --profile llm build
	else
		# Build only core services
		docker compose build devops-organizer nginx
	fi
	print_success "Images built successfully"
}

get_local_ip() {
    # Try to get the local IP address
    if command -v ip &> /dev/null; then
        LOCAL_IP=$(ip route get 8.8.8.8 | sed -n '/src/{s/.*src *\([^ ]*\).*/\1/p;q}')
    elif command -v ifconfig &> /dev/null; then
        LOCAL_IP=$(ifconfig | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d':' -f2)
    else
        LOCAL_IP="localhost"
    fi
    
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="localhost"
    fi
}

main() {
    print_header
    
    check_docker
    get_local_ip
    
    # Check for Docker Model availability
    DOCKER_MODEL_AVAILABLE=false
    if check_docker_model; then
        DOCKER_MODEL_AVAILABLE=true
        export ENABLE_LLM=true
    else
        export ENABLE_LLM=false
    fi
    
	# Optionally rebuild images
	if $BUILD; then
		build_images
	fi

	print_info "Starting DevOps Organizer management server..."
    
    # Start the services
    if $DOCKER_MODEL_AVAILABLE; then
        print_info "Starting all services including AI Assistant..."
        docker compose --profile llm up -d
    else
        print_info "Starting core services (without AI Assistant)..."
        docker compose up -d devops-organizer nginx
    fi
    
    # Wait a moment for services to start
    sleep 3
    
    print_success "Management server started successfully!"
    
    if $DOCKER_MODEL_AVAILABLE; then
        print_success "🤖 AI Assistant is enabled and available in the dashboard!"
    else
        print_warning "🤖 AI Assistant is disabled (Docker Model not available)"
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
    echo "  View logs:     docker-compose logs -f"
    echo "  Stop server:   docker-compose down"
    echo "  Restart:       docker-compose restart"
    echo
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Open http://localhost:8085 in your browser"
    echo "  2. Install agents on machines you want to monitor"
    echo "  3. Watch your infrastructure come to life!"
}

main "$@"
