# DevOps Organizer Agent

Lightweight agent that reports system, projects, Docker, K3s, and SSH info to the management server.

## Install & Run (All platforms)
1) Download from the management server: `http://[SERVER]:8085/download/agent.zip`
2) Unzip and install:
```bash
cd agent && ./simple-install.sh
```
3) Start the agent:
```bash
python3 ~/.devops-agent/simple-agent.py --server http://[SERVER]:8085 --name "my-machine"
```

Quick test mode:
```bash
python3 ~/.devops-agent/simple-agent.py --server http://[SERVER]:8085 --once
```

## Options
```bash
--server URL     # Management server URL (required)
--name NAME      # Agent name (default: hostname)
--interval SEC   # Report interval (default: 30)
--once           # Run once and exit
```

## Help
- Verify server: `curl http://[SERVER]:8085/api/system/info`
- If install fails: `cd agent && ./simple-install.sh`

Done. Download, install, run.