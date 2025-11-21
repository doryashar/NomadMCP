# NomadMCP

MCP server for automated task execution using OpenCode/CodeNomad with PR management and feedback loops.

## Overview

NomadMCP is an MCP (Model Context Protocol) server that automates coding tasks by:

1. Creating a new git branch for each task
2. Spawning an OpenCode server session
3. Sending the task to an AI agent
4. Waiting for the agent to create a pull request
5. Polling the PR for review feedback
6. Automatically iterating on feedback until the PR is merged
7. Cleaning up the branch when complete

Each task runs in its own isolated OpenCode session with a dedicated git branch, enabling parallel task execution without conflicts.

## Architecture

The server manages the complete lifecycle:

- **GitManager**: Validates repositories, creates/deletes branches
- **ProcessManager**: Spawns and manages OpenCode server processes
- **ClientManager**: HTTP client for OpenCode API communication
- **SessionManager**: Manages OpenCode session lifecycle
- **PRManager**: GitHub PR operations via `gh` CLI
- **TaskOrchestrator**: Coordinates the complete workflow

## Requirements

- **Python**: 3.10 or higher
- **OpenCode CLI**: Install with `npm install -g @opencode/cli`
- **GitHub CLI**: Install with `brew install gh` (macOS) or see [GitHub CLI docs](https://cli.github.com/)
- **Git repository**: The working directory must be a git repository
- **GitHub authentication**: Run `gh auth login` to authenticate

## Installation

1. Clone the repository:
```bash
git clone https://github.com/doryashar/NomadMCP.git
cd NomadMCP
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the MCP server in your Claude Code settings:

Add to your MCP settings configuration:
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

## Usage

### MCP Tool: `execute_task`

Execute a coding task in a new branch with automatic PR management.

**Parameters:**

- `task_description` (string, required): Description of the task to complete
- `working_directory` (string, required): Absolute path to the git repository
- `branch_name` (string, optional): Custom branch name (auto-generated if not provided)
- `timeout_minutes` (number, optional): Maximum time to wait for PR merge (default: 60)

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
User → MCP Tool Call → Task Orchestrator
  ↓
  1. Git validation (error if not a repo)
  2. Create new branch
  3. Spawn OpenCode server
  4. Create session via API
  5. Send task prompt
  ↓
  6. Poll for PR creation (check messages)
  7. Extract PR URL and number
  ↓
  8. Poll PR status every 30s
  ↓
  9. If merged:
     - Delete branch
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
