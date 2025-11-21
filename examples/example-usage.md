# Example Usage

## Basic Task Execution

Ask Claude to use the MCP tool:

```
Use the execute_task tool to add a new feature to my project:

Task Description: "Add a dark mode toggle to the settings page. The toggle should persist across sessions using localStorage."
Working Directory: /Users/username/projects/my-app
```

## Custom Branch Name

```
Use the execute_task tool:

Task Description: "Fix the authentication bug where users are logged out after page refresh"
Working Directory: /Users/username/projects/my-app
Branch Name: bugfix/auth-persistence
```

## With Custom Timeout

```
Use the execute_task tool with a longer timeout:

Task Description: "Refactor the entire database layer to use TypeORM instead of raw SQL queries"
Working Directory: /Users/username/projects/my-app
Timeout: 120 minutes
```

## Multiple Tasks in Parallel

You can execute multiple tasks in parallel by calling the tool multiple times. Each task will:
- Get its own branch
- Get its own OpenCode server instance
- Work independently
- Create separate PRs

```
Execute these three tasks in parallel:

1. execute_task:
   - Task: "Add user profile avatar upload"
   - Directory: /Users/username/projects/my-app
   - Branch: feature/avatar-upload

2. execute_task:
   - Task: "Implement email notifications for comments"
   - Directory: /Users/username/projects/my-app
   - Branch: feature/email-notifications

3. execute_task:
   - Task: "Add pagination to the user list"
   - Directory: /Users/username/projects/my-app
   - Branch: feature/user-pagination
```

## Expected Output

### Success Case

```
✓ Task completed successfully!

Branch: feature/dark-mode
PR: https://github.com/username/my-app/pull/123
PR Number: #123
Iterations: 2
Time: 847.3s

The PR has been merged and the branch has been deleted.
```

### Timeout Case

```
⏱ Task timed out

Branch: feature/complex-refactor
PR: https://github.com/username/my-app/pull/124
PR Number: #124
Iterations: 5
Time: 3600.0s

The PR was not merged within the timeout period (60 minutes).
You may want to check the PR manually and continue the review process.
```

### Failure Case

```
✗ Task failed

Branch: feature/broken-attempt
Error: Directory is not a git repository
Time: 0.2s

Please check the error message and try again.
```

## Monitoring Progress

### In CodeNomad Desktop

1. When NomadMCP starts an OpenCode server, note the port number from logs
2. Open CodeNomad desktop app
3. Click "Add Instance"
4. Enter `http://localhost:<port>` (e.g., `http://localhost:52301`)
5. Click "Connect"
6. View the session in real-time

### Via GitHub

1. Navigate to your repository on GitHub
2. Click "Pull requests"
3. Find the PR created by the agent
4. Monitor commits, comments, and merge status

### Via Command Line

```bash
# List all branches
git branch -a

# Check PR status
gh pr list

# View PR details
gh pr view <number>

# View PR comments
gh pr view <number> --comments
```

## Troubleshooting

### "OpenCode binary not found"

Install OpenCode CLI:
```bash
npm install -g @opencode/cli
```

### "gh command failed"

Authenticate with GitHub:
```bash
gh auth login
```

### "Directory is not a git repository"

Make sure you're pointing to a git repository:
```bash
cd /path/to/your/project
git status  # Should not error
```

### "Branch already exists"

Delete the existing branch:
```bash
git branch -D <branch-name>
```

Or use a different branch name in your task.
