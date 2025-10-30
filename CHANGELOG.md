# Changelog

All notable changes to this project will be documented in this file.

This is the first changelog entry.

## [v1.3.0] - 2025-10-30

### Added
- Agent ZIP download endpoint (`/download/agent.zip`) to package and serve the agent folder from the management server
- Download Agent ZIP button and simplified installation instructions in the Agents tab of the web dashboard
- `--build` flag to `start-server.sh` to rebuild Docker images before starting services
- Interactive prompt in `agent/simple-install.sh` to either run continuous monitoring immediately or display the command for later use

### Changed
- Simplified root `README.md` to be concise and action-focused with clear quick start instructions
- Streamlined `agent/README.md` to a minimal download → install → run guide for immediate usability
- Updated agent installation workflow to support downloading agent ZIP from management server UI

### Notes
This release focuses on improving agent distribution and installation workflow, making it easier for users to deploy agents on new machines directly from the management dashboard.

