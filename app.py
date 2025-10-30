#!/usr/bin/env python3
"""
DevOps Developer Organizer
A comprehensive tool for managing local projects, Docker containers, K3s clusters, and SSH keys.
"""

import os
import json
import subprocess
import platform
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
import io
import zipfile
import docker
from kubernetes import client, config
from datetime import datetime, timedelta
import threading
import sqlite3
import requests

app = Flask(__name__)

class AgentDataStore:
    """Store and manage agent data using SQLite"""
    
    def __init__(self, db_path='agents.db'):
        self.db_path = db_path
        self.init_database()
        self._cleanup_thread = threading.Timer(3600, self._cleanup_old_data)  # Cleanup every hour
        self._cleanup_thread.daemon = True
        self._cleanup_thread.start()
    
    def init_database(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Agents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    hostname TEXT,
                    platform TEXT,
                    architecture TEXT,
                    python_version TEXT,
                    registered_at TEXT,
                    last_seen TEXT,
                    capabilities TEXT,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            # System data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TEXT,
                    data TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Projects data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS projects_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TEXT,
                    data TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Docker data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS docker_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TEXT,
                    data TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # K3s data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS k3s_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TEXT,
                    data TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # SSH data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ssh_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TEXT,
                    data TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            conn.commit()
        finally:
            conn.close()
    
    def register_agent(self, agent_data):
        """Register a new agent"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO agents 
                (agent_id, agent_name, hostname, platform, architecture, python_version, 
                 registered_at, last_seen, capabilities, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            ''', (
                agent_data['agent_id'],
                agent_data['agent_name'],
                agent_data['hostname'],
                agent_data['platform'],
                agent_data['architecture'],
                agent_data['python_version'],
                agent_data['registered_at'],
                datetime.utcnow().isoformat(),
                json.dumps(agent_data['capabilities'])
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error registering agent: {e}")
            return False
        finally:
            conn.close()
    
    def update_agent_last_seen(self, agent_id):
        """Update agent last seen timestamp"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE agents SET last_seen = ? WHERE agent_id = ?
            ''', (datetime.utcnow().isoformat(), agent_id))
            conn.commit()
        except Exception as e:
            print(f"Error updating agent last seen: {e}")
        finally:
            conn.close()
    
    def store_agent_data(self, table, data):
        """Store agent data in specified table"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO {table} (agent_id, timestamp, data)
                VALUES (?, ?, ?)
            ''', (data['agent_id'], datetime.utcnow().isoformat(), json.dumps(data)))
            conn.commit()
            self.update_agent_last_seen(data['agent_id'])
        except Exception as e:
            print(f"Error storing agent data: {e}")
        finally:
            conn.close()
    
    def get_agents(self):
        """Get all registered agents"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM agents ORDER BY last_seen DESC')
            rows = cursor.fetchall()
            
            agents = []
            for row in rows:
                agent = {
                    'agent_id': row[0],
                    'agent_name': row[1],
                    'hostname': row[2],
                    'platform': row[3],
                    'architecture': row[4],
                    'python_version': row[5],
                    'registered_at': row[6],
                    'last_seen': row[7],
                    'capabilities': json.loads(row[8]) if row[8] else {},
                    'status': self._get_agent_status(row[7])
                }
                agents.append(agent)
            
            return agents
        except Exception as e:
            print(f"Error getting agents: {e}")
            return []
        finally:
            conn.close()
    
    def get_latest_agent_data(self, table, agent_id=None):
        """Get latest data from specified table"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            if agent_id:
                cursor.execute(f'''
                    SELECT data FROM {table} 
                    WHERE agent_id = ? 
                    ORDER BY timestamp DESC LIMIT 1
                ''', (agent_id,))
                row = cursor.fetchone()
                return json.loads(row[0]) if row else None
            else:
                # Get latest data from each agent
                cursor.execute(f'''
                    SELECT agent_id, data FROM {table} t1
                    WHERE timestamp = (
                        SELECT MAX(timestamp) FROM {table} t2 
                        WHERE t2.agent_id = t1.agent_id
                    )
                    ORDER BY timestamp DESC
                ''')
                rows = cursor.fetchall()
                return [json.loads(row[1]) for row in rows]
        
        except Exception as e:
            print(f"Error getting agent data: {e}")
            return [] if not agent_id else None
        finally:
            conn.close()
    
    def get_all_agent_data(self, table):
        """Get all data from specified table grouped by agent"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT agent_id, data FROM {table} t1
                WHERE timestamp = (
                    SELECT MAX(timestamp) FROM {table} t2 
                    WHERE t2.agent_id = t1.agent_id
                )
                ORDER BY timestamp DESC
            ''')
            rows = cursor.fetchall()
            
            result = {}
            for row in rows:
                agent_id = row[0]
                data = json.loads(row[1])
                result[agent_id] = data
            
            return result
        except Exception as e:
            print(f"Error getting all agent data: {e}")
            return {}
        finally:
            conn.close()
    
    def _get_agent_status(self, last_seen_str):
        """Determine agent status based on last seen time"""
        try:
            last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
            now = datetime.utcnow()
            time_diff = now - last_seen
            
            if time_diff < timedelta(minutes=2):
                return 'online'
            elif time_diff < timedelta(minutes=10):
                return 'warning'
            else:
                return 'offline'
        except Exception:
            return 'unknown'
    
    def _cleanup_old_data(self):
        """Clean up old data (keep last 24 hours)"""
        cutoff_time = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        
        tables = ['system_data', 'projects_data', 'docker_data', 'k3s_data', 'ssh_data']
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            for table in tables:
                cursor.execute(f'DELETE FROM {table} WHERE timestamp < ?', (cutoff_time,))
            conn.commit()
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
        finally:
            conn.close()
        
        # Schedule next cleanup
        self._cleanup_thread = threading.Timer(3600, self._cleanup_old_data)
        self._cleanup_thread.daemon = True
        self._cleanup_thread.start()


class AgentManager:
    """Manage agents and their data"""
    
    def __init__(self):
        self.data_store = AgentDataStore()
    
    def register_agent(self, agent_data):
        """Register a new agent"""
        return self.data_store.register_agent(agent_data)
    
    def get_agents(self):
        """Get all agents"""
        return self.data_store.get_agents()
    
    def store_system_data(self, data):
        """Store system data from agent"""
        self.data_store.store_agent_data('system_data', data)
    
    def store_projects_data(self, data):
        """Store projects data from agent"""
        self.data_store.store_agent_data('projects_data', data)
    
    def store_docker_data(self, data):
        """Store Docker data from agent"""
        self.data_store.store_agent_data('docker_data', data)
    
    def store_k3s_data(self, data):
        """Store K3s data from agent"""
        self.data_store.store_agent_data('k3s_data', data)
    
    def store_ssh_data(self, data):
        """Store SSH data from agent"""
        self.data_store.store_agent_data('ssh_data', data)
    
    def get_aggregated_system_info(self):
        """Get aggregated system information from all agents"""
        agents_data = self.data_store.get_all_agent_data('system_data')
        agents = self.data_store.get_agents()
        
        result = []
        for agent in agents:
            agent_id = agent['agent_id']
            system_data = agents_data.get(agent_id, {})
            
            result.append({
                'agent': agent,
                'system': system_data
            })
        
        return result
    
    def get_aggregated_projects(self):
        """Get aggregated projects from all agents"""
        return self.data_store.get_all_agent_data('projects_data')
    
    def get_aggregated_docker(self):
        """Get aggregated Docker data from all agents"""
        return self.data_store.get_all_agent_data('docker_data')
    
    def get_aggregated_k3s(self):
        """Get aggregated K3s data from all agents"""
        return self.data_store.get_all_agent_data('k3s_data')
    
    def get_aggregated_ssh(self):
        """Get aggregated SSH data from all agents"""
        return self.data_store.get_all_agent_data('ssh_data')


# Initialize agent manager
agent_manager = AgentManager()

class ProjectFinder:
    """Handle local project discovery and analysis"""
    
    def __init__(self):
        self.home_dir = Path.home()
        self.custom_path = None
    
    def set_custom_path(self, path):
        """Set custom search path"""
        self.custom_path = Path(path) if path else None
    
    def find_git_projects(self, search_path=None):
        """Find all Git repositories in the specified directory"""
        base_path = search_path or self.custom_path or self.home_dir
        projects = []
        
        try:
            # Use find command for better performance on Unix systems
            if platform.system() != 'Windows':
                result = subprocess.run(
                    ['find', str(base_path), '-name', '.git', '-type', 'd'],
                    capture_output=True, text=True, timeout=30
                )
                git_dirs = result.stdout.strip().split('\n') if result.stdout.strip() else []
            else:
                # Fallback for Windows
                git_dirs = []
                for root, dirs, files in os.walk(base_path):
                    if '.git' in dirs:
                        git_dirs.append(os.path.join(root, '.git'))
            
            for git_dir in git_dirs:
                if git_dir:
                    project_path = Path(git_dir).parent
                    project_info = self._analyze_project(project_path)
                    if project_info:
                        projects.append(project_info)
        
        except Exception as e:
            print(f"Error finding projects: {e}")
        
        return projects
    
    def _analyze_project(self, project_path):
        """Analyze a project directory for details"""
        try:
            project_info = {
                'name': project_path.name,
                'path': str(project_path),
                'size': self._calculate_size(project_path),
                'file_count': self._count_files(project_path),
                'project_type': self._detect_project_type(project_path),
                'libraries': self._find_libraries(project_path),
                'has_venv': self._check_venv(project_path),
                'git_branch': self._get_git_branch(project_path)
            }
            return project_info
        except Exception as e:
            print(f"Error analyzing project {project_path}: {e}")
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
            return round(total_size / (1024 * 1024), 2)  # Convert to MB
        except Exception:
            return 0
    
    def _count_files(self, path):
        """Count total files in directory"""
        try:
            count = 0
            for _, _, files in os.walk(path):
                count += len(files)
            return count
        except Exception:
            return 0
    
    def _detect_project_type(self, path):
        """Detect project type based on file extensions and config files"""
        type_indicators = {
            'python': ['.py', 'requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
            'javascript': ['.js', '.ts', 'package.json', 'node_modules'],
            'java': ['.java', 'pom.xml', 'build.gradle', '.gradle'],
            'csharp': ['.cs', '.csproj', '.sln'],
            'rust': ['.rs', 'Cargo.toml', 'Cargo.lock'],
            'go': ['.go', 'go.mod', 'go.sum'],
            'php': ['.php', 'composer.json'],
            'ruby': ['.rb', 'Gemfile'],
            'cpp': ['.cpp', '.cc', '.cxx', '.hpp', '.h', 'CMakeLists.txt'],
            'docker': ['Dockerfile', 'docker-compose.yml'],
            'terraform': ['.tf', '.tfvars']
        }
        
        detected_types = []
        
        try:
            # Check for specific files
            for file_path in path.rglob('*'):
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
        """Find libraries and dependencies in the project"""
        libraries = []
        
        try:
            # Python requirements
            req_files = ['requirements.txt', 'Pipfile', 'pyproject.toml']
            for req_file in req_files:
                req_path = path / req_file
                if req_path.exists():
                    libraries.extend(self._parse_python_requirements(req_path))
            
            # Node.js package.json
            package_json = path / 'package.json'
            if package_json.exists():
                libraries.extend(self._parse_package_json(package_json))
            
            # Go modules
            go_mod = path / 'go.mod'
            if go_mod.exists():
                libraries.extend(self._parse_go_mod(go_mod))
            
            # Rust Cargo.toml
            cargo_toml = path / 'Cargo.toml'
            if cargo_toml.exists():
                libraries.extend(self._parse_cargo_toml(cargo_toml))
        
        except Exception:
            pass
        
        return list(set(libraries))
    
    def _parse_python_requirements(self, file_path):
        """Parse Python requirements file"""
        libraries = []
        try:
            if file_path.name == 'requirements.txt':
                with open(file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            lib_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0]
                            libraries.append(lib_name)
            # Add parsing for other Python dependency files as needed
        except Exception:
            pass
        return libraries
    
    def _parse_package_json(self, file_path):
        """Parse Node.js package.json"""
        libraries = []
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if 'dependencies' in data:
                    libraries.extend(data['dependencies'].keys())
                if 'devDependencies' in data:
                    libraries.extend(data['devDependencies'].keys())
        except Exception:
            pass
        return libraries
    
    def _parse_go_mod(self, file_path):
        """Parse Go go.mod file"""
        libraries = []
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('require'):
                        # Simple parsing - can be improved
                        parts = line.split()
                        if len(parts) >= 2:
                            libraries.append(parts[1])
        except Exception:
            pass
        return libraries
    
    def _parse_cargo_toml(self, file_path):
        """Parse Rust Cargo.toml file"""
        libraries = []
        try:
            import toml
            with open(file_path, 'r') as f:
                data = toml.load(f)
                if 'dependencies' in data:
                    libraries.extend(data['dependencies'].keys())
        except Exception:
            pass
        return libraries
    
    def _check_venv(self, path):
        """Check if virtual environment exists"""
        venv_indicators = ['.venv', 'venv', '.env', 'env', '.virtualenv']
        for indicator in venv_indicators:
            if (path / indicator).exists():
                return True
        return False
    
    def _get_git_branch(self, path):
        """Get current Git branch"""
        try:
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=path, capture_output=True, text=True
            )
            return result.stdout.strip() if result.returncode == 0 else 'unknown'
        except Exception:
            return 'unknown'


class DockerManager:
    """Handle Docker operations"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            print(f"Docker client initialization failed: {e}")
            self.client = None
    
    def get_running_containers(self):
        """Get list of running containers"""
        if not self.client:
            return []
        
        try:
            containers = self.client.containers.list()
            return [{
                'id': container.short_id,
                'name': container.name,
                'image': container.image.tags[0] if container.image.tags else 'unknown',
                'status': container.status,
                'ports': self._format_ports(container.ports),
                'created': container.attrs['Created']
            } for container in containers]
        except Exception as e:
            print(f"Error getting running containers: {e}")
            return []
    
    def get_stopped_containers(self):
        """Get list of stopped containers"""
        if not self.client:
            return []
        
        try:
            containers = self.client.containers.list(all=True, filters={'status': 'exited'})
            return [{
                'id': container.short_id,
                'name': container.name,
                'image': container.image.tags[0] if container.image.tags else 'unknown',
                'status': container.status,
                'created': container.attrs['Created']
            } for container in containers]
        except Exception as e:
            print(f"Error getting stopped containers: {e}")
            return []
    
    def get_images(self):
        """Get list of Docker images"""
        if not self.client:
            return []
        
        try:
            images = self.client.images.list()
            return [{
                'id': image.short_id,
                'tags': image.tags,
                'size': round(image.attrs['Size'] / (1024 * 1024), 2),  # MB
                'created': image.attrs['Created']
            } for image in images]
        except Exception as e:
            print(f"Error getting images: {e}")
            return []
    
    def _format_ports(self, ports):
        """Format container ports for display"""
        if not ports:
            return []
        
        formatted_ports = []
        for container_port, host_configs in ports.items():
            if host_configs:
                for config in host_configs:
                    formatted_ports.append(f"{config['HostPort']}:{container_port}")
            else:
                formatted_ports.append(container_port)
        
        return formatted_ports


class K3sManager:
    """Handle K3s/Kubernetes operations"""
    
    def __init__(self):
        try:
            config.load_kube_config()
            self.v1 = client.CoreV1Api()
        except Exception as e:
            print(f"Kubernetes client initialization failed: {e}")
            self.v1 = None
    
    def get_nodes(self):
        """Get list of cluster nodes"""
        if not self.v1:
            return []
        
        try:
            nodes = self.v1.list_node()
            return [{
                'name': node.metadata.name,
                'status': self._get_node_status(node),
                'roles': self._get_node_roles(node),
                'version': node.status.node_info.kubelet_version,
                'os': node.status.node_info.os_image
            } for node in nodes.items]
        except Exception as e:
            print(f"Error getting nodes: {e}")
            return []
    
    def get_pods(self):
        """Get list of active pods"""
        if not self.v1:
            return []
        
        try:
            pods = self.v1.list_pod_for_all_namespaces()
            return [{
                'name': pod.metadata.name,
                'namespace': pod.metadata.namespace,
                'status': pod.status.phase,
                'node': pod.spec.node_name,
                'containers': len(pod.spec.containers),
                'restarts': sum([container.restart_count or 0 for container in pod.status.container_statuses or []])
            } for pod in pods.items if pod.status.phase == 'Running']
        except Exception as e:
            print(f"Error getting pods: {e}")
            return []
    
    def _get_node_status(self, node):
        """Get node status"""
        for condition in node.status.conditions:
            if condition.type == 'Ready':
                return 'Ready' if condition.status == 'True' else 'NotReady'
        return 'Unknown'
    
    def _get_node_roles(self, node):
        """Get node roles"""
        roles = []
        if node.metadata.labels:
            for label, value in node.metadata.labels.items():
                if 'node-role.kubernetes.io' in label:
                    role = label.split('/')[-1]
                    if role:
                        roles.append(role)
        return roles if roles else ['worker']


class SSHKeyManager:
    """Handle SSH key operations"""
    
    def __init__(self):
        self.ssh_dir = Path.home() / '.ssh'
    
    def get_ssh_keys(self):
        """Get list of SSH keys and their types"""
        keys = []
        
        if not self.ssh_dir.exists():
            return keys
        
        try:
            # Common SSH key patterns
            key_patterns = ['id_*', '*_rsa', '*_dsa', '*_ecdsa', '*_ed25519']
            
            for pattern in key_patterns:
                for key_file in self.ssh_dir.glob(pattern):
                    if key_file.is_file() and not key_file.name.endswith('.pub'):
                        key_info = self._analyze_key(key_file)
                        if key_info:
                            keys.append(key_info)
        
        except Exception as e:
            print(f"Error getting SSH keys: {e}")
        
        return keys
    
    def _analyze_key(self, key_path):
        """Analyze SSH key file"""
        try:
            # Check if corresponding public key exists
            pub_key_path = key_path.with_suffix(key_path.suffix + '.pub')
            has_public = pub_key_path.exists()
            
            # Try to determine key type
            key_type = self._determine_key_type(key_path, pub_key_path if has_public else None)
            
            return {
                'name': key_path.name,
                'path': str(key_path),
                'type': key_type,
                'has_public': has_public,
                'size': key_path.stat().st_size,
                'modified': key_path.stat().st_mtime
            }
        
        except Exception as e:
            print(f"Error analyzing key {key_path}: {e}")
            return None
    
    def _determine_key_type(self, private_key_path, public_key_path=None):
        """Determine SSH key type"""
        try:
            # First try to read from public key if available
            if public_key_path and public_key_path.exists():
                with open(public_key_path, 'r') as f:
                    content = f.read().strip()
                    if content.startswith('ssh-rsa'):
                        return 'RSA'
                    elif content.startswith('ssh-dss'):
                        return 'DSA'
                    elif content.startswith('ssh-ed25519'):
                        return 'Ed25519'
                    elif content.startswith('ecdsa-sha2'):
                        return 'ECDSA'
            
            # Fallback to filename analysis
            name = private_key_path.name.lower()
            if 'rsa' in name:
                return 'RSA'
            elif 'dsa' in name:
                return 'DSA'
            elif 'ed25519' in name:
                return 'Ed25519'
            elif 'ecdsa' in name:
                return 'ECDSA'
            
            return 'Unknown'
        
        except Exception:
            return 'Unknown'


# Initialize managers
project_finder = ProjectFinder()
docker_manager = DockerManager()
k3s_manager = K3sManager()
ssh_manager = SSHKeyManager()


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/download/agent.zip')
def download_agent_zip():
    """Serve the agent folder as a zip download"""
    try:
        base_dir = Path(__file__).resolve().parent
        agent_dir = base_dir / 'agent'
        if not agent_dir.exists() or not agent_dir.is_dir():
            return jsonify({'status': 'error', 'message': 'Agent directory not found'}), 404

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in agent_dir.rglob('*'):
                if file_path.is_file():
                    # Write file with relative path inside zip
                    arcname = file_path.relative_to(base_dir)
                    zf.write(file_path, arcname.as_posix())

        memory_file.seek(0)
        filename = f"agent-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to create agent zip: {str(e)}'}), 500


@app.route('/api/projects')
def api_projects():
    """API endpoint for aggregated projects from all agents"""
    projects_data = agent_manager.get_aggregated_projects()
    
    # Flatten projects from all agents
    all_projects = []
    for agent_id, data in projects_data.items():
        if 'projects' in data:
            for project in data['projects']:
                project['agent_id'] = agent_id
                project['agent_name'] = data.get('agent_name', 'Unknown')
                all_projects.append(project)
    
    return jsonify(all_projects)


@app.route('/api/docker/containers')
def api_docker_containers():
    """API endpoint for aggregated Docker containers from all agents"""
    docker_data = agent_manager.get_aggregated_docker()
    
    aggregated = {'running': [], 'stopped': []}
    
    for agent_id, data in docker_data.items():
        if data.get('available', False) and 'containers' in data:
            # Add agent info to each container
            for container in data['containers'].get('running', []):
                container['agent_id'] = agent_id
                container['agent_name'] = data.get('agent_name', 'Unknown')
                aggregated['running'].append(container)
            
            for container in data['containers'].get('stopped', []):
                container['agent_id'] = agent_id
                container['agent_name'] = data.get('agent_name', 'Unknown')
                aggregated['stopped'].append(container)
    
    return jsonify(aggregated)


@app.route('/api/docker/images')
def api_docker_images():
    """API endpoint for aggregated Docker images from all agents"""
    docker_data = agent_manager.get_aggregated_docker()
    
    all_images = []
    for agent_id, data in docker_data.items():
        if data.get('available', False) and 'images' in data:
            for image in data['images']:
                image['agent_id'] = agent_id
                image['agent_name'] = data.get('agent_name', 'Unknown')
                all_images.append(image)
    
    return jsonify(all_images)


@app.route('/api/k3s/nodes')
def api_k3s_nodes():
    """API endpoint for aggregated K3s nodes from all agents"""
    k3s_data = agent_manager.get_aggregated_k3s()
    
    all_nodes = []
    for agent_id, data in k3s_data.items():
        if data.get('available', False) and 'nodes' in data:
            for node in data['nodes']:
                node['agent_id'] = agent_id
                node['agent_name'] = data.get('agent_name', 'Unknown')
                all_nodes.append(node)
    
    return jsonify(all_nodes)


@app.route('/api/k3s/pods')
def api_k3s_pods():
    """API endpoint for aggregated K3s pods from all agents"""
    k3s_data = agent_manager.get_aggregated_k3s()
    
    all_pods = []
    for agent_id, data in k3s_data.items():
        if data.get('available', False) and 'pods' in data:
            for pod in data['pods']:
                pod['agent_id'] = agent_id
                pod['agent_name'] = data.get('agent_name', 'Unknown')
                all_pods.append(pod)
    
    return jsonify(all_pods)


@app.route('/api/ssh/keys')
def api_ssh_keys():
    """API endpoint for aggregated SSH keys from all agents"""
    ssh_data = agent_manager.get_aggregated_ssh()
    
    all_keys = []
    for agent_id, data in ssh_data.items():
        if 'ssh_keys' in data:
            for key in data['ssh_keys']:
                key['agent_id'] = agent_id
                key['agent_name'] = data.get('agent_name', 'Unknown')
                all_keys.append(key)
    
    return jsonify(all_keys)


# Agent API Endpoints
@app.route('/api/agents/register', methods=['POST'])
def api_agent_register():
    """Register a new agent"""
    try:
        agent_data = request.get_json()
        if agent_manager.register_agent(agent_data):
            return jsonify({'status': 'success', 'message': 'Agent registered'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to register agent'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/agents/system', methods=['POST'])
def api_agent_system():
    """Receive system data from agent"""
    try:
        data = request.get_json()
        agent_manager.store_system_data(data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/agents/projects', methods=['POST'])
def api_agent_projects():
    """Receive projects data from agent"""
    try:
        data = request.get_json()
        agent_manager.store_projects_data(data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/agents/docker', methods=['POST'])
def api_agent_docker():
    """Receive Docker data from agent"""
    try:
        data = request.get_json()
        agent_manager.store_docker_data(data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/agents/k3s', methods=['POST'])
def api_agent_k3s():
    """Receive K3s data from agent"""
    try:
        data = request.get_json()
        agent_manager.store_k3s_data(data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/agents/ssh', methods=['POST'])
def api_agent_ssh():
    """Receive SSH data from agent"""
    try:
        data = request.get_json()
        agent_manager.store_ssh_data(data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/agents')
def api_agents_list():
    """Get list of all agents"""
    return jsonify(agent_manager.get_agents())

@app.route('/api/system/info')
def api_system_info():
    """API endpoint for aggregated system information from all agents"""
    return jsonify(agent_manager.get_aggregated_system_info())


# AI Assistant API Endpoints
@app.route('/api/ai/status')
def api_ai_status():
    """Check if LLM is available"""
    try:
        # Try to connect to the LLM service
        response = requests.get('http://model-runner.docker.internal/health', timeout=5)
        if response.status_code == 200:
            return jsonify({'status': 'online', 'message': 'AI Assistant ready'})
        else:
            return jsonify({'status': 'offline', 'message': 'LLM service not responding'})
    except requests.exceptions.ConnectionError:
        return jsonify({'status': 'offline', 'message': 'Docker Model not available - please enable in Docker Desktop'})
    except requests.exceptions.Timeout:
        return jsonify({'status': 'offline', 'message': 'LLM service timeout'})
    except Exception as e:
        return jsonify({'status': 'offline', 'message': f'LLM check failed: {str(e)}'})


@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    """Handle chat messages with AI assistant"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'success': False, 'error': 'No message provided'})
        
        # Get current agent data for context
        context_data = get_agent_context()
        
        # Prepare system prompt with agent data context
        system_prompt = f"""You are a DevOps AI assistant. You have access to real-time infrastructure data from multiple agents. 

Current Infrastructure Data:
{context_data}

Answer questions about this infrastructure data only. Be helpful, concise, and specific. If asked about something not in the data, politely explain that you can only discuss the current infrastructure data shown above.

User Question: {user_message}"""

        # Send request to LLM
        llm_response = requests.post(
            'http://model-runner.docker.internal/engines/llama.cpp/v1/chat/completions',
            headers={'Content-Type': 'application/json'},
            json={
                "model": "ai/llama3.2:1B-Q8_0",
                "messages": [
                    {"role": "system", "content": system_prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=30
        )
        
        if llm_response.status_code == 200:
            llm_data = llm_response.json()
            assistant_response = llm_data['choices'][0]['message']['content']
            return jsonify({'success': True, 'response': assistant_response})
        else:
            return jsonify({'success': False, 'error': f'LLM service error: {llm_response.status_code}'})
            
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'LLM service timeout'})
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'Cannot connect to LLM service'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'})


def get_agent_context():
    """Get current agent data formatted for AI context"""
    try:
        # Get agents
        agents = agent_manager.get_agents()
        
        # Get aggregated data
        projects_data = agent_manager.get_aggregated_projects()
        docker_data = agent_manager.get_aggregated_docker()
        k3s_data = agent_manager.get_aggregated_k3s()
        ssh_data = agent_manager.get_aggregated_ssh()
        
        # Format context
        context = f"""
AGENTS ({len(agents)} total):
"""
        
        for agent in agents:
            context += f"- {agent['agent_name']} ({agent['hostname']}) - Status: {agent['status']} - Platform: {agent['platform']} {agent['architecture']}\n"
        
        # Projects summary
        total_projects = sum(len(data.get('projects', [])) for data in projects_data.values())
        context += f"\nPROJECTS ({total_projects} total):\n"
        
        project_types = {}
        for agent_id, data in projects_data.items():
            agent_name = next((a['agent_name'] for a in agents if a['agent_id'] == agent_id), 'Unknown')
            projects = data.get('projects', [])
            context += f"- {agent_name}: {len(projects)} projects\n"
            
            for project in projects:
                for ptype in project.get('project_type', []):
                    project_types[ptype] = project_types.get(ptype, 0) + 1
        
        context += f"Project Types: {', '.join(f'{k}({v})' for k, v in project_types.items())}\n"
        
        # Docker summary
        total_running = sum(len(data.get('containers', {}).get('running', [])) for data in docker_data.values() if data.get('available'))
        total_stopped = sum(len(data.get('containers', {}).get('stopped', [])) for data in docker_data.values() if data.get('available'))
        total_images = sum(len(data.get('images', [])) for data in docker_data.values() if data.get('available'))
        
        context += f"\nDOCKER:\n- Running containers: {total_running}\n- Stopped containers: {total_stopped}\n- Images: {total_images}\n"
        
        # K3s summary
        total_nodes = sum(len(data.get('nodes', [])) for data in k3s_data.values() if data.get('available'))
        total_pods = sum(len(data.get('pods', [])) for data in k3s_data.values() if data.get('available'))
        
        context += f"\nKUBERNETES:\n- Nodes: {total_nodes}\n- Running pods: {total_pods}\n"
        
        # SSH summary
        total_keys = sum(len(data.get('ssh_keys', [])) for data in ssh_data.values())
        context += f"\nSSH KEYS: {total_keys} total\n"
        
        return context
        
    except Exception as e:
        return f"Error getting context: {str(e)}"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8085, debug=True)
