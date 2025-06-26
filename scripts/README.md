# 5G Slicing Manager - Utility Scripts

This directory contains various utility scripts to help manage and interact with the 5G Slicing Manager platform.

## Available Scripts

### Core Management

- `start.sh` - Start all services using Docker Compose
- `stop.sh` - Stop all running services
- `clean.sh` - Stop services and remove all data (reset to clean state)
- `init.sh` - Initialize the environment and set up required configurations
- `healthcheck.sh` - Check the health and status of all services
- `monitor.sh` - Monitor system resources and service metrics in real-time

### Backup & Recovery

- `backup.sh` - Create a complete backup of the system
- `restore.sh` - Restore the system from a backup

### NS-3 Integration

- `test-ns3-integration.sh` - Test the NS-3 integration with the 5G Slicing Manager
- `setup-ns3-simulation.sh` - Set up and configure the NS-3 simulation environment

### Database Management

- `db-migrate.sh` - Run database migrations
- `db-backup.sh` - Backup the database
- `db-restore.sh` - Restore the database from a backup

### Monitoring & Logging

- `logs.sh` - View logs for all or specific services
- `setup-monitoring.sh` - Set up monitoring stack (Prometheus, Grafana, etc.)
- `setup-logging.sh` - Set up centralized logging (ELK stack)

## Usage Examples

### Start the Platform

```bash
# Start all services
./start.sh

# Start in detached mode (no logs)
./start.sh --detach
```

### Check Service Status

```bash
# Basic health check
./healthcheck.sh

# Monitor in real-time
./monitor.sh --watch
```

### Backup and Restore

```bash
# Create a backup
./backup.sh

# Restore from the latest backup
./restore.sh $(ls -t backups/*.tar.gz | head -1)
```

### NS-3 Integration Testing

```bash
# Run a 5-minute test with default settings
./test-ns3-integration.sh

# Customize test parameters
./test-ns3-integration.sh --duration 600 --interval 2.0 --slice-id my-test-slice
```

## Script Development Guidelines

1. **Shebang**: Always start scripts with `#!/bin/bash`
2. **Error Handling**: Use `set -euo pipefail` for better error handling
3. **Logging**: Use the provided logging functions for consistent output
4. **Documentation**: Include a help section in each script
5. **Configuration**: Use environment variables for configuration
6. **Dependencies**: Check for required commands at the start of the script

## Dependencies

Most scripts require the following tools to be installed:

- `docker` and `docker-compose`
- `curl` for API interactions
- `jq` for JSON processing
- Common Unix utilities (`grep`, `awk`, `sed`, etc.)

## License





