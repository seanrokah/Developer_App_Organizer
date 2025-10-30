#!/usr/bin/env python3
"""
DevOps Organizer Simple Agent
A lightweight monitoring agent that sends data to the management server
"""

import os
import json
import time
import platform
import subprocess
import socket
import uuid
import logging
import logging.handlers
from pathlib import Path
import requests
import psutil
import argparse
import sys

# Import optional libraries at top
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None

try:
    from kubernetes import client, config
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None


def setup_logging():
    """Setup logging to both console and file"""
    # Create log directory if it doesn't exist
    log_dir = Path.home() / '.devops-agent'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'agent.log'
    
    # Configure logging format
    log_format = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    
    # File handler with rotation (10MB, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    
    # Root logger configuration
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


# Initialize logger
logger = setup_logging()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='DevOps Organizer Simple Agent')
    parser.add_argument('--server', help='Management server URL')
    parser.add_argument('--name', help='Agent name (default: hostname)')
    parser.add_argument('--interval', type=int, default=30, help='Report interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interactive', action='store_true', help='Force interactive mode')
    
    args = parser.parse_args()
    
    # Use interactive mode if no server provided or explicitly requested
    if not args.server or args.interactive:
        try:
            server, agent_name, run_once, interval = get_user_input()
        except KeyboardInterrupt:
            print("\n\n❌ Cancelled by user")
            sys.exit(0)
    else:
        server = args.server
        agent_name = args.name
        run_once = args.once
        interval = args.interval
    
    print(f"\n🚀 Starting DevOps Organizer Agent...")
    
    # Create and run agent
    try:
        agent = SimpleAgent(
            management_server_url=server,
            agent_name=agent_name
        )
        
        if run_once:
            print("🔍 Running test connection...")
            success = agent.run_once()
            if success:
                print("✅ Test completed successfully!")
            else:
                print("❌ Test failed - check server connection")
            sys.exit(0 if success else 1)
        else:
            print(f"🔄 Starting continuous monitoring (interval: {interval}s)")
            print("💡 Press Ctrl+C to stop")
            agent.run_continuous(interval)
    except KeyboardInterrupt:
        print("\n\n🛑 Agent stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Agent error: {e}")
        sys.exit(1)


class SimpleAgent:
    """Simplified agent that collects and reports system data"""
    
    def __init__(self, management_server_url, agent_name=None):
        self.management_server_url = management_server_url.rstrip('/')
        self.agent_id = str(uuid.uuid4())
        self.agent_name = agent_name or socket.gethostname()
        
        logger.info(f"Agent initialized: {self.agent_name} ({self.agent_id})")
    
    def register_agent(self):
        """Register agent with management server"""
        try:
            registration_data = {
                'agent_id': self.agent_id,
                'agent_name': self.agent_name,
                'hostname': socket.gethostname(),
                'platform': platform.system(),
                'architecture': platform.machine(),
                'python_version': platform.python_version(),
                'registered_at': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'capabilities': {
                    'projects': True,
                    'docker': self._docker_available(),
                    'k3s': self._kubectl_available(),
                    'ssh': True
                }
            }
            
            response = requests.post(
                f"{self.management_server_url}/api/agents/register",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Agent registered successfully")
                return True
            else:
                logger.error(f"Registration failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            return False
    
    def _docker_available(self):
        """Check if Docker is available"""
        if not DOCKER_AVAILABLE:
            return False
        try:
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False
    
    def _kubectl_available(self):
        """Check if Kubernetes/K3s is available"""
        if not KUBERNETES_AVAILABLE:
            return False
        try:
            # Try to load kubeconfig and check connection
            config.load_kube_config()
            # Try to get API version to verify connection
            v1 = client.CoreV1Api()
            v1.get_api_versions()
            return True
        except Exception:
            return False
    
    def collect_system_info(self):
        """Collect system information"""
        try:
            return {
                'agent_id': self.agent_id,
                'agent_name': self.agent_name,
                'hostname': socket.gethostname(),
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'platform': platform.system(),
                'architecture': platform.machine(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_total': round(psutil.virtual_memory().total / (1024**3), 2),
                'memory_available': round(psutil.virtual_memory().available / (1024**3), 2),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_total': round(psutil.disk_usage('/').total / (1024**3), 2),
                'disk_used': round(psutil.disk_usage('/').used / (1024**3), 2),
                'disk_percent': psutil.disk_usage('/').percent,
                'uptime': time.time() - psutil.boot_time(),
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }
        except Exception as e:
            logger.error(f"Error collecting system info: {e}")
            return {}
    
    def collect_projects(self):
        """Collect project information"""
        try:
            projects = self._find_git_projects()
            return {
                'agent_id': self.agent_id,
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'projects': projects,
                'total_projects': len(projects)
            }
        except Exception as e:
            logger.error(f"Error collecting projects: {e}")
            return {'agent_id': self.agent_id, 'projects': [], 'error': str(e)}
    
    def _find_git_projects(self):
        """Find Git repositories"""
        projects = []
        base_path = Path.home()
        
        try:
            # Simple search - look for .git directories
            for git_dir in base_path.rglob('.git'):
                if git_dir.is_dir():
                    project_path = git_dir.parent
                    project_info = self._analyze_project(project_path)
                    if project_info:
                        projects.append(project_info)
                        if len(projects) >= 20:  # Limit for POC
                            break
        except Exception as e:
            logger.error(f"Error finding projects: {e}")
        
        return projects
    
    def _analyze_project(self, project_path):
        """Analyze a project directory"""
        try:
            return {
                'name': project_path.name,
                'path': str(project_path),
                'size': self._calculate_size(project_path),
                'file_count': self._count_files(project_path),
                'project_type': self._detect_project_type(project_path),
                'libraries': self._find_libraries(project_path),
                'has_venv': self._check_venv(project_path),
                'git_branch': self._get_git_branch(project_path)
            }
        except Exception as e:
            logger.error(f"Error analyzing project {project_path}: {e}")
            return None
    
    def _calculate_size(self, path):
        """Calculate directory size in MB"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, FileNotFoundError):
                        continue
                if total_size > 500 * 1024 * 1024:  # Stop at 500MB for performance
                    break
            return round(total_size / (1024 * 1024), 2)
        except Exception:
            return 0
    
    def _count_files(self, path):
        """Count files in directory"""
        try:
            count = 0
            for _, _, files in os.walk(path):
                count += len(files)
                if count > 10000:  # Limit for performance
                    break
            return min(count, 10000)
        except Exception:
            return 0
    
    def _detect_project_type(self, path):
        """Detect project type"""
        type_indicators = {
            'python': ['.py', 'requirements.txt', 'setup.py', 'pyproject.toml'],
            'javascript': ['.js', '.ts', 'package.json'],
            'java': ['.java', 'pom.xml', 'build.gradle'],
            'go': ['.go', 'go.mod'],
            'rust': ['.rs', 'Cargo.toml'],
            'docker': ['Dockerfile', 'docker-compose.yml']
        }
        
        detected_types = []
        try:
            for file_path in path.iterdir():
                if file_path.is_file():
                    file_name = file_path.name.lower()
                    file_ext = file_path.suffix.lower()
                    
                    for proj_type, indicators in type_indicators.items():
                        for indicator in indicators:
                            if indicator.startswith('.') and file_ext == indicator:
                                detected_types.append(proj_type)
                            elif not indicator.startswith('.') and file_name == indicator.lower():
                                detected_types.append(proj_type)
        except Exception:
            pass
        
        return list(set(detected_types)) if detected_types else ['unknown']
    
    def _find_libraries(self, path):
        """Find project libraries"""
        libraries = []
        try:
            # Python requirements
            req_file = path / 'requirements.txt'
            if req_file.exists():
                with open(req_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            lib_name = line.split('==')[0].split('>=')[0].split('<=')[0]
                            libraries.append(lib_name)
                            if len(libraries) >= 10:  # Limit for POC
                                break
            
            # Node.js package.json
            package_json = path / 'package.json'
            if package_json.exists():
                with open(package_json, 'r') as f:
                    data = json.load(f)
                    if 'dependencies' in data:
                        libraries.extend(list(data['dependencies'].keys())[:5])
        except Exception:
            pass
        
        return libraries[:10]  # Limit to 10 libraries
    
    def _check_venv(self, path):
        """Check for virtual environment"""
        venv_indicators = ['.venv', 'venv', '.env', 'env']
        for indicator in venv_indicators:
            if (path / indicator).exists():
                return True
        return False
    
    def _get_git_branch(self, path):
        """Get current Git branch"""
        try:
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=path, capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else 'unknown'
        except Exception:
            return 'unknown'
    
    def collect_docker_info(self):
        """Collect Docker information"""
        try:
            if not self._docker_available():
                return {'agent_id': self.agent_id, 'available': False}
            
            client = docker.from_env()
            
            # Get running containers
            running_containers = []
            for container in client.containers.list():
                running_containers.append({
                    'id': container.short_id,
                    'name': container.name,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'status': container.status,
                    'created': container.attrs['Created']
                })
            
            # Get stopped containers (limited)
            stopped_containers = []
            for container in client.containers.list(all=True, filters={'status': 'exited'})[:5]:
                stopped_containers.append({
                    'id': container.short_id,
                    'name': container.name,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'status': container.status,
                    'created': container.attrs['Created']
                })
            
            # Get images (limited)
            images = []
            for image in client.images.list()[:10]:
                images.append({
                    'id': image.short_id,
                    'tags': image.tags,
                    'size': round(image.attrs['Size'] / (1024 * 1024), 2),
                    'created': image.attrs['Created']
                })
            
            return {
                'agent_id': self.agent_id,
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'available': True,
                'containers': {
                    'running': running_containers,
                    'stopped': stopped_containers
                },
                'images': images
            }
        except Exception as e:
            logger.error(f"Error collecting Docker info: {e}")
            return {'agent_id': self.agent_id, 'available': False, 'error': str(e)}
    
    def collect_ssh_info(self):
        """Collect SSH key information"""
        try:
            ssh_dir = Path.home() / '.ssh'
            keys = []
            
            if ssh_dir.exists():
                for key_file in ssh_dir.glob('id_*'):
                    if key_file.is_file() and not key_file.name.endswith('.pub'):
                        keys.append({
                            'name': key_file.name,
                            'path': str(key_file),
                            'type': self._determine_key_type(key_file),
                            'has_public': (key_file.with_suffix(key_file.suffix + '.pub')).exists(),
                            'size': key_file.stat().st_size,
                            'modified': key_file.stat().st_mtime
                        })
            
            return {
                'agent_id': self.agent_id,
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'ssh_keys': keys
            }
        except Exception as e:
            logger.error(f"Error collecting SSH info: {e}")
            return {'agent_id': self.agent_id, 'ssh_keys': [], 'error': str(e)}
    
    def _determine_key_type(self, key_path):
        """Determine SSH key type"""
        name = key_path.name.lower()
        if 'rsa' in name:
            return 'RSA'
        elif 'ed25519' in name:
            return 'Ed25519'
        elif 'ecdsa' in name:
            return 'ECDSA'
        elif 'dsa' in name:
            return 'DSA'
        return 'Unknown'
    
    def send_data(self, endpoint, data):
        """Send data to management server"""
        try:
            response = requests.post(
                f"{self.management_server_url}/api/agents/{endpoint}",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Data sent successfully to {endpoint}")
                return True
            else:
                logger.error(f"Failed to send data to {endpoint}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending data to {endpoint}: {e}")
            return False
    
    def run_once(self):
        """Run a single data collection and send cycle"""
        logger.info("Starting data collection cycle")
        
        # Register agent
        if not self.register_agent():
            logger.error("Failed to register agent")
            return False
        
        # Collect and send system info
        system_data = self.collect_system_info()
        if system_data:
            self.send_data('system', system_data)
        
        # Collect and send projects
        logger.info("Collecting projects...")
        projects_data = self.collect_projects()
        if projects_data:
            self.send_data('projects', projects_data)
        
        # Collect and send Docker info
        logger.info("Collecting Docker info...")
        docker_data = self.collect_docker_info()
        if docker_data:
            self.send_data('docker', docker_data)
        
        # Collect and send SSH info
        logger.info("Collecting SSH info...")
        ssh_data = self.collect_ssh_info()
        if ssh_data:
            self.send_data('ssh', ssh_data)
        
        logger.info("Data collection cycle completed")
        return True
    
    def run_continuous(self, interval=30):
        """Run continuous monitoring"""
        logger.info(f"Starting continuous monitoring (interval: {interval}s)")
        
        try:
            while True:
                self.run_once()
                logger.info(f"Sleeping for {interval} seconds...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Agent stopped by user")
        except Exception as e:
            logger.error(f"Agent error: {e}")


def get_user_input():
    """Interactive mode to get user input"""
    print("=" * 60)
    print("🚀 DevOps Organizer Agent - Interactive Setup")
    print("=" * 60)
    print()
    
    # Get server URL
    while True:
        server = input("📡 Management server URL (e.g., http://192.168.1.100:8085): ").strip()
        if server:
            if not server.startswith(('http://', 'https://')):
                server = 'http://' + server
            break
        print("❌ Server URL is required!")
    
    # Get agent name
    agent_name = input(f"🏷️  Agent name (press Enter for '{socket.gethostname()}'): ").strip()
    if not agent_name:
        agent_name = None
    
    # Get execution mode
    print("\n🔧 Execution mode:")
    print("1. Test connection (run once and exit)")
    print("2. Continuous monitoring")
    
    while True:
        mode = input("Choose mode (1 or 2): ").strip()
        if mode in ['1', '2']:
            break
        print("❌ Please enter 1 or 2")
    
    run_once = (mode == '1')
    interval = 30
    
    # Get interval if continuous mode
    if not run_once:
        while True:
            interval_input = input(f"⏱️  Report interval in seconds (press Enter for {interval}): ").strip()
            if not interval_input:
                break
            try:
                interval = int(interval_input)
                if interval < 10:
                    print("❌ Interval must be at least 10 seconds")
                    continue
                break
            except ValueError:
                print("❌ Please enter a valid number")
    
    print("\n" + "=" * 60)
    print("📋 Configuration Summary:")
    print(f"   Server: {server}")
    print(f"   Agent: {agent_name or socket.gethostname()}")
    print(f"   Mode: {'Test run (once)' if run_once else f'Continuous (every {interval}s)'}")
    print("=" * 60)
    
    # Confirm
    confirm = input("\n✅ Start agent with these settings? (Y/n): ").strip().lower()
    if confirm and confirm not in ['y', 'yes']:
        print("❌ Cancelled by user")
        sys.exit(0)
    
    return server, agent_name, run_once, interval


if __name__ == '__main__':
    main()
