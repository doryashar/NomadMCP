# Docker Deployment for NomadMCP

This guide explains how to run NomadMCP in Docker containers.

## Quick Start

### 1. Build the Image

```bash
docker-compose build
```

### 2. Configure Environment

Create a `.env` file:

```bash
# Path to your code repositories
REPO_PATH=/path/to/your/repos

# Configuration
LOG_LEVEL=INFO
MAX_PARALLEL_TASKS=5
DEFAULT_TIMEOUT=60
USE_WORKTREES=true
BRANCH_PREFIX=task
```

### 3. Run the Container

```bash
docker-compose up -d
```

## Usage

### Run a Task

The container runs the MCP server, which you can connect to from your Claude Code client.

Configure your MCP client to connect to the Docker container (adjust based on your MCP transport):

```json
{
  "mcpServers": {
    "nomad-mcp": {
      "command": "docker",
      "args": ["exec", "-i", "nomad-mcp", "python", "-m", "src.server"]
    }
  }
}
```

### Development Mode

For development with hot reload:

```bash
docker-compose --profile dev up nomad-mcp-dev
```

This mounts your local source code into the container.

## Volume Mounts

The Docker setup mounts several important directories:

### Repositories
```yaml
- ${REPO_PATH}:/repos
```
Mount your code repositories here. Tasks will work on these repos.

### Git Credentials
```yaml
- ~/.gitconfig:/root/.gitconfig:ro
- ~/.ssh:/root/.ssh:ro
```
Git configuration and SSH keys for authentication.

### GitHub CLI
```yaml
- ~/.config/gh:/root/.config/gh:ro
```
GitHub CLI authentication for PR operations.

### Logs
```yaml
- ./logs:/var/log/nomad-mcp
```
Server logs are persisted here.

### Data
```yaml
- ./data:/var/lib/nomad-mcp
```
Task persistence data.

## Authentication

### Git Authentication

The container uses your host's git config and SSH keys. Make sure:

1. Your SSH keys are set up:
   ```bash
   ls -la ~/.ssh/
   ```

2. Your git config is correct:
   ```bash
   git config --list
   ```

### GitHub CLI Authentication

Authenticate GitHub CLI on your host before running the container:

```bash
gh auth login
```

The authentication token will be mounted into the container.

## Configuration

### Environment Variables

All configuration can be done via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NOMAD_MCP_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `NOMAD_MCP_LOG_FILE` | `/var/log/nomad-mcp/server.log` | Log file path |
| `NOMAD_MCP_MAX_PARALLEL_TASKS` | `5` | Maximum parallel tasks |
| `NOMAD_MCP_DEFAULT_TIMEOUT` | `60` | Default task timeout (minutes) |
| `NOMAD_MCP_USE_WORKTREES` | `true` | Use git worktrees for parallel tasks |
| `NOMAD_MCP_BRANCH_PREFIX` | `task` | Prefix for auto-generated branches |
| `NOMAD_MCP_PERSISTENCE_FILE` | `/var/lib/nomad-mcp/tasks.json` | Task persistence file |

### Config File

Alternatively, mount a config file:

```yaml
volumes:
  - ./config.json:/app/config.json:ro
```

Then set the environment variable:
```bash
NOMAD_MCP_CONFIG_FILE=/app/config.json
```

## Troubleshooting

### Container Logs

View logs:
```bash
docker-compose logs -f nomad-mcp
```

### Server Logs

Check the server log file:
```bash
cat ./logs/server.log
```

### Exec into Container

For debugging:
```bash
docker-compose exec nomad-mcp bash
```

### Common Issues

**Git authentication fails:**
- Ensure SSH keys are mounted correctly
- Check SSH key permissions: `chmod 600 ~/.ssh/id_rsa`
- Verify git config is mounted

**GitHub CLI fails:**
- Run `gh auth status` on host to verify authentication
- Ensure `~/.config/gh` is mounted

**OpenCode not found:**
- The image includes OpenCode CLI by default
- Verify with: `docker-compose exec nomad-mcp opencode --version`

**Permission denied:**
- Ensure mounted volumes have correct permissions
- May need to adjust UID/GID in Dockerfile

## Building for Production

### Multi-stage Build

For a smaller production image:

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
# ... copy from builder
```

### Security Considerations

1. **Use secrets management** for sensitive credentials
2. **Run as non-root user**
3. **Use read-only mounts** where possible
4. **Scan images** for vulnerabilities
5. **Update base images** regularly

## Kubernetes Deployment

For Kubernetes, see `k8s/` directory (if available) or adapt the Docker compose file:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nomad-mcp
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: nomad-mcp
        image: nomad-mcp:latest
        env:
        - name: NOMAD_MCP_MAX_PARALLEL_TASKS
          value: "10"
        volumeMounts:
        - name: repos
          mountPath: /repos
```

## Monitoring

### Health Checks

Add health check to docker-compose:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Prometheus Metrics

(To be implemented: expose metrics endpoint)

## Performance Tuning

### Resource Limits

In docker-compose:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

### Parallel Tasks

Adjust based on available resources:
```bash
NOMAD_MCP_MAX_PARALLEL_TASKS=10
```

## Backup and Recovery

### Backup Task Data

```bash
# Backup task persistence
cp ./data/tasks.json ./backups/tasks-$(date +%Y%m%d).json

# Backup logs
tar czf ./backups/logs-$(date +%Y%m%d).tar.gz ./logs/
```

### Restore

```bash
# Restore task data
cp ./backups/tasks-20250121.json ./data/tasks.json

# Restart container
docker-compose restart nomad-mcp
```

## Updates

### Update the Image

```bash
# Pull latest code
git pull

# Rebuild image
docker-compose build --no-cache

# Restart with new image
docker-compose up -d
```

### Rolling Updates

For zero-downtime updates (requires orchestration like Kubernetes or Docker Swarm).
