# NomadMCP

MCP server and CLI tool for automated task execution using OpenCode/CodeNomad with parallel execution, git worktrees, and PR management.

## Overview

NomadMCP is an MCP (Model Context Protocol) server and CLI tool that automates coding tasks by:

1. Creating isolated workspaces for each task (git worktrees or branches)
2. Spawning OpenCode server sessions
3. Sending tasks to AI agents
4. Waiting for agents to create pull requests
5. Polling PRs for review feedback
6. Automatically iterating on feedback until PRs are merged
7. Cleaning up workspaces when complete

### Key Features

✨ **Parallel Task Execution** - Run multiple tasks simultaneously with configurable limits
🌳 **Git Worktrees** - Use worktrees for true parallel work without conflicts
🐳 **Docker Support** - Full containerization with Docker and Docker Compose
🖥️ **CLI Tool** - Standalone CLI for running tasks and viewing progress in CodeNomad
⚙️ **Flexible Configuration** - Configure via env vars, JSON files, or defaults
🔄 **Automatic PR Iteration** - Continuously addresses review feedback until merge

## Architecture

The system manages the complete lifecycle with these components:

- **GitManager**: Repository validation, branch/worktree operations
- **ProcessManager**: Spawns and manages OpenCode server processes
- **ClientManager**: HTTP client for OpenCode API communication
- **SessionManager**: Manages OpenCode session lifecycle
- **PRManager**: GitHub PR operations via `gh` CLI
- **TaskOrchestrator**: Coordinates the complete workflow
- **TaskQueue**: Manages parallel execution with configurable limits
- **CLI Tool**: Standalone interface for task execution

## Requirements

- **Python**: 3.10 or higher
- **OpenCode CLI**: Install with `npm install -g @opencode/cli`
- **GitHub CLI**: Install with `brew install gh` (macOS) or see [GitHub CLI docs](https://cli.github.com/)
- **Git repository**: The working directory must be a git repository
- **GitHub authentication**: Run `gh auth login` to authenticate

## Installation

### Option 1: Standard Installation

1. Clone the repository:
```bash
git clone https://github.com/doryashar/NomadMCP.git
cd NomadMCP
```

2. Run the installation script:
```bash
./install.sh
```

Or install manually:
```bash
pip install -r requirements.txt
```

3. Install CLI tool (optional):
```bash
pip install -e .
```

### Option 2: Docker Installation

```bash
docker-compose build
docker-compose up -d
```

See [docker-README.md](docker-README.md) for detailed Docker instructions.

## Configuration

Configure via environment variables or `config.json`:

```bash
# Parallel execution
export NOMAD_MCP_MAX_PARALLEL_TASKS=5

# Use git worktrees (recommended for parallel tasks)
export NOMAD_MCP_USE_WORKTREES=true

# Task settings
export NOMAD_MCP_DEFAULT_TIMEOUT=60
export NOMAD_MCP_BRANCH_PREFIX=task

# Logging
export NOMAD_MCP_LOG_LEVEL=INFO
```

Or create `config.json` (see `config.example.json`)

## Usage

### Option 1: MCP Server (via Claude Code)

Configure the MCP server in your Claude Code settings:

```json
{
  "mcpServers": {
    "nomad-mcp": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/NomadMCP"
    }
  }
}
```

Then use the `execute_task` tool:

**Parameters:**

- `task_description` (string, required): Description of the task to complete
- `working_directory` (string, optional): Absolute path to git repository (defaults to current directory)
- `branch_name` (string, optional): Custom branch name (auto-generated if not provided)
- `timeout_minutes` (number, optional): Maximum time to wait for PR merge (default: 60)

### Option 2: CLI Tool (Standalone)

Run tasks directly from the command line:

```bash
# Single task
nomad-cli -d "Add dark mode toggle to settings"

# Multiple tasks in parallel
nomad-cli -d "Add dark mode" -d "Fix login bug" -d "Update docs"

# Tasks from JSON file
nomad-cli --tasks-file tasks.json

# Specify working directory
nomad-cli -d "Add feature" --dir /path/to/repo

# Don't open CodeNomad GUI
nomad-cli -d "Add feature" --no-gui
```

**Tasks file format** (`tasks.json`):

```json
[
  {
    "id": "task-1",
    "description": "Add dark mode toggle",
    "branch_name": "feature/dark-mode",
    "timeout_minutes": 60
  },
  {
    "id": "task-2",
    "description": "Fix authentication bug",
    "working_directory": "/path/to/other/repo"
  }
]
```

The CLI automatically:
- Opens CodeNomad GUI to show all active sessions
- Lists server ports for manual connection
- Runs tasks in parallel (respecting max_parallel_tasks config)
- Outputs results as JSON (with `--output` flag)

**Example:**

```
Use the execute_task tool to add a new feature to my project:

Task: "Add a dark mode toggle to the settings page with persistence"
Working Directory: /Users/username/projects/my-app
Branch Name: feature/dark-mode
```

**Workflow:**

1. ✓ Validates the directory is a git repository
2. ✓ Creates branch `feature/dark-mode`
3. ✓ Starts OpenCode server in that directory
4. ✓ Creates a new session
5. ✓ Sends task prompt to the AI agent
6. ✓ Agent implements the feature and creates a PR
7. ✓ Monitors PR for merge or review comments
8. ✓ If comments exist, sends them back to the agent
9. ✓ Agent addresses feedback and updates the PR
10. ✓ Repeats steps 7-9 until PR is merged
11. ✓ Deletes branch and cleans up session

## How It Works

### Task Execution Flow

```
User → MCP Tool/CLI → Task Queue → Task Orchestrator
  ↓
  1. Git validation (error if not a repo)
  2. Create worktree (or branch if worktrees disabled)
  3. Spawn OpenCode server in worktree directory
  4. Create session via API
  5. Send task prompt
  ↓
  6. Poll for PR creation (check messages)
  7. Extract PR URL and number
  ↓
  8. Poll PR status every 30s
  ↓
  9. If merged:
     - Remove worktree/delete branch
     - Close session
     - Kill server
     - Return success
  ↓
  10. If review comments:
      - Format comments
      - Send to session
      - Wait for agent to update PR
      - Go to step 8
  ↓
  11. If timeout:
      - Return timeout status
      - Leave PR open for manual review
```

### Parallel Execution & Git Worktrees

**Why Worktrees?**

When running multiple tasks in parallel on the same repository, traditional branches can cause conflicts:
- Can't checkout different branches simultaneously
- File changes from one task affect others
- Agents may overwrite each other's work

**Git worktrees** solve this by creating separate working directories:
```bash
repo/
├── .git/
├── main-code/          # Main worktree
└── .git/worktrees_nomad/
    ├── task_abc123/    # Task 1's isolated workspace
    └── task_def456/    # Task 2's isolated workspace
```

Each worktree:
- Has its own branch checked out
- Has completely separate files
- Can be worked on simultaneously
- Shares the same git database

**Configuration:**
```bash
# Enable worktrees (default: true)
export NOMAD_MCP_USE_WORKTREES=true

# Set max parallel tasks
export NOMAD_MCP_MAX_PARALLEL_TASKS=5
```

**When to use branches instead:**
- Single task execution
- Sequential workflow
- Simpler mental model
- Set `NOMAD_MCP_USE_WORKTREES=false`

### OpenCode vs CodeNomad

**OpenCode** is the underlying CLI/server that performs AI coding work:
- Runs as `opencode serve`
- Exposes HTTP API
- Manages sessions and messages

**CodeNomad** is a desktop GUI (Electron app) that:
- Spawns OpenCode servers
- Provides a visual interface
- Manages multiple instances

**NomadMCP** does the same thing as CodeNomad but programmatically:
- Spawns OpenCode servers directly
- Connects via HTTP API
- No GUI needed
- Ideal for automation

## Viewing Sessions in CodeNomad

Since NomadMCP spawns OpenCode servers directly, you can connect CodeNomad to these servers to view sessions:

1. Start a task with NomadMCP (this spawns an OpenCode server on a random port)
2. Open CodeNomad desktop app
3. Add a new instance pointing to `http://localhost:<port>`
4. View the session in real-time

The port is displayed in logs when the server starts.

## Project Structure

```
NomadMCP/
├── src/
│   ├── __init__.py           # Package init
│   ├── __main__.py           # Entry point
│   ├── server.py             # MCP server implementation
│   ├── types.py              # Data models and types
│   ├── git_manager.py        # Git operations
│   ├── process_manager.py    # OpenCode process management
│   ├── client_manager.py     # OpenCode API client
│   ├── session_manager.py    # Session lifecycle
│   ├── pr_manager.py         # GitHub PR operations
│   └── task_orchestrator.py  # Main orchestration logic
├── pyproject.toml            # Project metadata
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Error Handling

The server handles various error scenarios:

- **Not a git repo**: Returns error immediately
- **Branch exists**: Returns error to avoid conflicts
- **OpenCode not installed**: Clear error message with installation instructions
- **GitHub CLI not authenticated**: Error with authentication instructions
- **Server spawn failure**: Cleanup and detailed error
- **Session creation failure**: Cleanup and retry logic
- **PR timeout**: Returns timeout status, leaves PR open
- **Server crash**: Detection and graceful cleanup

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
ruff check src/
```

## Limitations

- Requires manual GitHub authentication (`gh auth login`)
- PR polling interval is fixed at 30 seconds
- One task per OpenCode server instance
- No persistence - if the MCP server restarts, active tasks are lost

## Future Enhancements

- [ ] Persistent task tracking across restarts
- [ ] Parallel task execution with resource limits
- [ ] Configurable polling intervals
- [ ] Support for other git hosting platforms (GitLab, Bitbucket)
- [ ] WebSocket support for real-time updates
- [ ] Task queue management
- [ ] Integration with CodeNomad's desktop app for automatic instance registration

## License

MIT

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Support

For issues or questions, please open an issue on GitHub.
