# DevOps Developer Organizer

Centralized dashboard to monitor multiple development machines: projects, Docker, K3s, and SSH keys. Lightweight agents report to a Flask-based management server.

## Quick Start

### 1) Start Management Server
```bash
./start-server.sh
```
Open `http://localhost:8085`.

### 2) Add a New Machine (Agent)
- From the dashboard, click “Download Agent ZIP” (or fetch: `http://[SERVER]:8085/download/agent.zip`).
- Copy to the target machine and unzip it.
- Install and run:
```bash
cd agent && ./simple-install.sh
python3 ~/.devops-agent/simple-agent.py --server http://[SERVER]:8085 --name "my-machine"
```

Optional: quick test mode
```bash
python3 ~/.devops-agent/simple-agent.py --server http://[SERVER]:8085 --once
```

### 3) Docker Deployment (Optional)
```bash
docker run -d \
  --name devops-organizer \
  -p 8085:8085 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  ghcr.io/seanrokah/devops-organizer:latest
```

## Agent CLI
```bash
--server URL     # Management server URL (required)
--name NAME      # Agent name (default: hostname)
--interval SEC   # Report interval (default: 30)
--once           # Run once and exit
```

## Troubleshooting
- Test server: `curl http://[SERVER]:8085/api/system/info`
- Test agent once: `python3 ~/.devops-agent/simple-agent.py --server http://[SERVER]:8085 --once`
- Ensure port 8085 is reachable.

## Structure
```
Developer_App_Organizer/
├── app.py                    # Flask management server
├── docker-compose.yml        # Docker orchestration
├── Dockerfile               # Container image
├── nginx.conf               # Reverse proxy config
├── start-server.sh          # Server startup script
├── requirements.txt         # Python dependencies
├── CHANGELOG.md             # Version history
├── README.md                # This file
├── static/                  # Web assets
│   ├── css/
│   └── js/
├── templates/               # HTML templates
├── docs/                    # Documentation
│   └── PROJECT_OVERVIEW.md  # Detailed project overview
└── agent/                   # Agent system
    ├── simple-agent.py
    ├── simple-install.sh
    └── requirements.txt
```

That's it. Install the server, download the agent zip, run the agent.
