"""MCP server implementation for NomadMCP."""

import asyncio
import uuid
from typing import Any
from mcp.server import Server
from mcp.types import Tool, TextContent

from .types import Task
from .git_manager import GitManager
from .process_manager import ProcessManager
from .client_manager import ClientManager
from .session_manager import SessionManager
from .pr_manager import PRManager
from .task_orchestrator import TaskOrchestrator
from .task_queue import TaskQueue
from .config import get_config
from .logging_config import setup_logging, get_logger

logger = get_logger(__name__)


class NomadMCPServer:
    """MCP server for automated task execution."""

    def __init__(self):
        """Initialize the MCP server."""
        # Load configuration
        self.config = get_config()

        # Setup logging
        setup_logging(
            level=self.config.logging.level,
            log_file=self.config.logging.log_file,
        )

        logger.info("Initializing NomadMCP server")
        logger.debug(f"Configuration: {self.config.model_dump()}")

        self.app = Server("nomad-mcp")

        # Initialize managers
        self.git_manager = GitManager()
        self.process_manager = ProcessManager()
        self.client_manager = ClientManager()
        self.session_manager = SessionManager(self.client_manager)
        self.pr_manager = PRManager()

        # Initialize orchestrator
        self.orchestrator = TaskOrchestrator(
            git_manager=self.git_manager,
            process_manager=self.process_manager,
            client_manager=self.client_manager,
            session_manager=self.session_manager,
            pr_manager=self.pr_manager,
            use_worktrees=self.config.task.use_worktrees,
        )

        # Initialize task queue
        self.task_queue = TaskQueue(
            orchestrator=self.orchestrator,
            max_parallel=self.config.task.max_parallel_tasks,
        )

        logger.info(f"Task queue initialized with max_parallel={self.config.task.max_parallel_tasks}")
        logger.info(f"Using worktrees: {self.config.task.use_worktrees}")

        # Register handlers
        self._register_handlers()

        logger.info("NomadMCP server initialized successfully")

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.app.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="execute_task",
                    description=(
                        "Execute a coding task in a new git branch using OpenCode/CodeNomad. "
                        "Each task creates a new OpenCode session and branch, completes the task, "
                        "creates a pull request, and iterates on feedback until the PR is merged. "
                        "\n\n"
                        "Requirements:\n"
                        "- The working directory must be a git repository\n"
                        "- OpenCode CLI must be installed (npm install -g @opencode/cli)\n"
                        "- GitHub CLI (gh) must be installed and authenticated\n"
                        "\n"
                        "The tool will:\n"
                        "1. Validate the directory is a git repository\n"
                        "2. Create a new branch for the task\n"
                        "3. Start an OpenCode server in that directory\n"
                        "4. Create a session and send the task description\n"
                        "5. Wait for the agent to create a PR\n"
                        "6. Poll the PR for merge status\n"
                        "7. If there are review comments, send them back to the agent\n"
                        "8. Repeat until the PR is merged or timeout is reached\n"
                        "9. Clean up the branch and session on success"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_description": {
                                "type": "string",
                                "description": "Description of the task to complete",
                            },
                            "working_directory": {
                                "type": "string",
                                "description": "Path to the git repository (absolute path). Defaults to current directory if not provided.",
                            },
                            "branch_name": {
                                "type": "string",
                                "description": (
                                    "Name for the new branch (optional, auto-generated if not provided)"
                                ),
                            },
                            "timeout_minutes": {
                                "type": "number",
                                "description": "Maximum time in minutes to wait for PR merge (default: 60)",
                                "default": 60,
                            },
                        },
                        "required": ["task_description"],
                    },
                )
            ]

        @self.app.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            if name != "execute_task":
                raise ValueError(f"Unknown tool: {name}")

            logger.info(f"Received tool call: {name}")
            logger.debug(f"Arguments: {arguments}")

            # Extract arguments
            task_description = arguments.get("task_description")
            working_directory = arguments.get("working_directory")
            branch_name = arguments.get("branch_name")
            timeout_minutes = arguments.get("timeout_minutes", self.config.task.default_timeout_minutes)

            # Validate task description
            if not task_description:
                error_msg = "Error: task_description is required"
                logger.error(error_msg)
                return [
                    TextContent(
                        type="text",
                        text=error_msg,
                    )
                ]

            # Default working directory to current directory
            if not working_directory:
                import os
                working_directory = os.getcwd()
                logger.info(f"Using current directory as working directory: {working_directory}")

            # Generate branch name if not provided
            if not branch_name:
                task_id = str(uuid.uuid4())[:8]
                branch_name = f"{self.config.task.branch_prefix}/{task_id}"
            else:
                task_id = branch_name

            logger.info(f"Creating task: {task_id} in {working_directory} on branch {branch_name}")

            # Create task
            task = Task(
                id=task_id,
                description=task_description,
                working_directory=working_directory,
                branch_name=branch_name,
                timeout_minutes=timeout_minutes,
            )

            # Submit task to queue
            logger.info(f"Submitting task: {task_id} to queue")
            await self.task_queue.submit_task(task)

            # Wait for task to complete with timeout
            # Add 10 minute buffer to task timeout to allow for cleanup
            mcp_timeout = (timeout_minutes + 10) * 60
            logger.info(f"Waiting for task {task_id} to complete (timeout: {mcp_timeout}s)")

            try:
                result = await self.task_queue.wait_for_task(task_id, timeout=mcp_timeout)
                logger.info(f"Task {task_id} completed with status: {result.status}")
            except asyncio.TimeoutError:
                logger.error(f"MCP tool call timed out for task {task_id} after {mcp_timeout}s")
                # Cancel the task
                await self.task_queue.cancel_task(task_id)
                return [
                    TextContent(
                        type="text",
                        text=f"""✗ MCP tool call timed out

Task ID: {task_id}
Branch: {branch_name}
Timeout: {mcp_timeout}s

The task did not complete within the MCP timeout period. The task has been cancelled.
This may indicate a problem with the OpenCode server or the task itself."""
                    )
                ]

            # Format response
            if result.status.value == "completed":
                response = f"""✓ Task completed successfully!

Branch: {branch_name}
PR: {result.pr_url}
PR Number: #{result.pr_number}
Iterations: {result.iterations}
Time: {result.elapsed_time:.1f}s

The PR has been merged and the branch has been deleted."""
            elif result.status.value == "timeout":
                response = f"""⏱ Task timed out

Branch: {branch_name}
PR: {result.pr_url}
PR Number: #{result.pr_number}
Iterations: {result.iterations}
Time: {result.elapsed_time:.1f}s

The PR was not merged within the timeout period ({timeout_minutes} minutes).
You may want to check the PR manually and continue the review process."""
            else:
                response = f"""✗ Task failed

Branch: {branch_name}
Error: {result.error}
Time: {result.elapsed_time:.1f}s

Please check the error message and try again."""

            return [TextContent(type="text", text=response)]

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.session_manager.cleanup_all()
        await self.client_manager.destroy_all()
        await self.process_manager.cleanup_all()

    def run(self) -> None:
        """Run the MCP server."""
        import mcp

        async def _run():
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await self.app.run(
                    read_stream,
                    write_stream,
                    self.app.create_initialization_options(),
                )

        try:
            asyncio.run(_run())
        finally:
            asyncio.run(self.cleanup())


def main():
    """Main entry point."""
    server = NomadMCPServer()
    server.run()


if __name__ == "__main__":
    main()
