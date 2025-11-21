# NomadMCP Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm (for OpenCode CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCode CLI
RUN npm install -g @opencode/cli

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Configure git (required for git operations)
RUN git config --global user.name "NomadMCP" \
    && git config --global user.email "nomad@mcp.local" \
    && git config --global init.defaultBranch main

# Create directories for logs and persistence
RUN mkdir -p /var/log/nomad-mcp /var/lib/nomad-mcp

# Set environment variables
ENV NOMAD_MCP_LOG_FILE=/var/log/nomad-mcp/server.log \
    NOMAD_MCP_LOG_LEVEL=INFO \
    NOMAD_MCP_PERSISTENCE_FILE=/var/lib/nomad-mcp/tasks.json

# Expose port (if MCP server needs HTTP - adjust as needed)
# EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["python", "-m", "src.server"]
