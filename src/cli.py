"""CLI for running NomadMCP tasks outside of MCP server."""

import asyncio
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

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


class NomadCLI:
    """CLI for NomadMCP task execution."""

    def __init__(self):
        """Initialize CLI."""
        self.config = get_config()
        setup_logging(
            level=self.config.logging.level,
            log_file=self.config.logging.log_file,
        )

        # Initialize managers
        self.git_manager = GitManager()
        self.process_manager = ProcessManager()
        self.client_manager = ClientManager()
        self.session_manager = SessionManager(self.client_manager)
        self.pr_manager = PRManager()

        # Initialize orchestrator
        self.orchestrator = TaskOrchestrator(
            git_manager=self.git_manager,
            client_manager=self.client_manager,
            process_manager=self.process_manager,
            session_manager=self.session_manager,
            pr_manager=self.pr_manager,
            use_worktrees=self.config.task.use_worktrees,
        )

        # Initialize task queue
        self.task_queue = TaskQueue(
            orchestrator=self.orchestrator,
            max_parallel=self.config.task.max_parallel_tasks,
        )

        self.server_ports: List[int] = []

    async def run_tasks(
        self,
        tasks: List[dict],
        working_directory: Optional[str] = None,
        open_codenomad: bool = True,
    ) -> List[dict]:
        """Run multiple tasks.

        Args:
            tasks: List of task dictionaries with 'description', optional 'branch_name', 'timeout_minutes'
            working_directory: Default working directory for all tasks
            open_codenomad: Whether to open CodeNomad GUI

        Returns:
            List of task results
        """
        if working_directory is None:
            working_directory = os.getcwd()

        logger.info(f"Running {len(tasks)} tasks in {working_directory}")
        logger.info(f"Max parallel tasks: {self.config.task.max_parallel_tasks}")
        logger.info(f"Using worktrees: {self.config.task.use_worktrees}")

        # Submit all tasks
        task_ids = []
        for i, task_def in enumerate(tasks):
            task_id = task_def.get("id", f"task-{i+1}")
            branch_name = task_def.get("branch_name", f"{self.config.task.branch_prefix}/{task_id}")
            timeout = task_def.get("timeout_minutes", self.config.task.default_timeout_minutes)

            task = Task(
                id=task_id,
                description=task_def["description"],
                working_directory=task_def.get("working_directory", working_directory),
                branch_name=branch_name,
                timeout_minutes=timeout,
            )

            logger.info(f"Submitting task {task_id}: {task.description[:50]}...")
            await self.task_queue.submit_task(task)
            task_ids.append(task_id)

        # Collect server ports for CodeNomad
        await asyncio.sleep(2)  # Give time for servers to start
        self.server_ports = list(self.process_manager.processes.keys())

        # Open CodeNomad if requested
        if open_codenomad and self.server_ports:
            self._open_codenomad()

        # Wait for all tasks to complete
        logger.info(f"Waiting for {len(task_ids)} tasks to complete...")
        results = []
        for task_id in task_ids:
            try:
                result = await self.task_queue.wait_for_task(task_id)
                results.append({
                    "task_id": task_id,
                    "status": result.status.value,
                    "pr_url": result.pr_url,
                    "pr_number": result.pr_number,
                    "error": result.error,
                    "iterations": result.iterations,
                    "elapsed_time": result.elapsed_time,
                })
                logger.info(f"Task {task_id} completed: {result.status.value}")
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                results.append({
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                })

        return results

    def _open_codenomad(self):
        """Open CodeNomad and add instances for the running servers."""
        logger.info("Opening CodeNomad...")

        # Check if CodeNomad is installed
        codenomad_app = self._find_codenomad()

        if not codenomad_app:
            logger.warning("CodeNomad not found. Skipping GUI open.")
            logger.info("Server ports: " + ", ".join(str(p) for p in self.server_ports))
            logger.info("You can manually connect CodeNomad to these ports.")
            return

        # Open CodeNomad
        try:
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", "-a", codenomad_app])
            elif sys.platform == "linux":
                subprocess.Popen([codenomad_app])
            elif sys.platform == "win32":
                subprocess.Popen([codenomad_app])

            logger.info(f"CodeNomad opened. Connect to ports: {self.server_ports}")
            logger.info("Add instances in CodeNomad:")
            for port in self.server_ports:
                logger.info(f"  - http://localhost:{port}")

        except Exception as e:
            logger.error(f"Failed to open CodeNomad: {e}")
            logger.info(f"Manually open CodeNomad and connect to ports: {self.server_ports}")

    def _find_codenomad(self) -> Optional[str]:
        """Find CodeNomad application.

        Returns:
            Path to CodeNomad or None if not found
        """
        if sys.platform == "darwin":  # macOS
            locations = [
                "/Applications/CodeNomad.app",
                os.path.expanduser("~/Applications/CodeNomad.app"),
            ]
            for loc in locations:
                if os.path.exists(loc):
                    return loc

        elif sys.platform == "linux":
            # Check common locations for AppImage
            locations = [
                os.path.expanduser("~/Applications/CodeNomad.AppImage"),
                "/usr/local/bin/codenomad",
                "/usr/bin/codenomad",
            ]
            for loc in locations:
                if os.path.exists(loc):
                    return loc

        elif sys.platform == "win32":
            # Check Program Files
            locations = [
                os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "CodeNomad\\CodeNomad.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs\\CodeNomad\\CodeNomad.exe"),
            ]
            for loc in locations:
                if os.path.exists(loc):
                    return loc

        return None

    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        await self.task_queue.cancel_all()
        await self.session_manager.cleanup_all()
        await self.client_manager.destroy_all()
        await self.process_manager.cleanup_all()


async def main_async():
    """Async main function."""
    parser = argparse.ArgumentParser(
        description="NomadMCP CLI - Run automated coding tasks with OpenCode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single task
  nomad-cli -d "Add dark mode toggle to settings"

  # Run multiple tasks
  nomad-cli -d "Add dark mode" -d "Fix login bug" -d "Update docs"

  # Run tasks from JSON file
  nomad-cli --tasks-file tasks.json

  # Specify working directory
  nomad-cli -d "Add feature" --dir /path/to/repo

  # Don't open CodeNomad GUI
  nomad-cli -d "Add feature" --no-gui

Tasks file format (JSON):
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
        """
    )

    parser.add_argument(
        "-d", "--description",
        action="append",
        dest="descriptions",
        help="Task description (can be specified multiple times)"
    )
    parser.add_argument(
        "--tasks-file",
        type=str,
        help="Path to JSON file with task definitions"
    )
    parser.add_argument(
        "--dir",
        type=str,
        help="Working directory (defaults to current directory)"
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Don't open CodeNomad GUI"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON)"
    )

    args = parser.parse_args()

    # Build task list
    tasks = []

    if args.tasks_file:
        with open(args.tasks_file, "r") as f:
            tasks = json.load(f)
        logger.info(f"Loaded {len(tasks)} tasks from {args.tasks_file}")

    if args.descriptions:
        for i, desc in enumerate(args.descriptions):
            tasks.append({
                "id": f"task-{i+1}",
                "description": desc,
            })

    if not tasks:
        parser.print_help()
        print("\nError: No tasks specified. Use -d or --tasks-file.")
        sys.exit(1)

    # Run tasks
    cli = NomadCLI()
    try:
        results = await cli.run_tasks(
            tasks=tasks,
            working_directory=args.dir,
            open_codenomad=not args.no_gui,
        )

        # Print summary
        print("\n" + "="*60)
        print("TASK EXECUTION SUMMARY")
        print("="*60)

        for result in results:
            status_symbol = "✓" if result["status"] == "completed" else "✗"
            print(f"\n{status_symbol} Task: {result['task_id']}")
            print(f"  Status: {result['status']}")
            if result.get("pr_url"):
                print(f"  PR: {result['pr_url']}")
            if result.get("error"):
                print(f"  Error: {result['error']}")
            if result.get("elapsed_time"):
                print(f"  Time: {result['elapsed_time']:.1f}s")

        # Save results if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to: {args.output}")

    finally:
        await cli.cleanup()


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
