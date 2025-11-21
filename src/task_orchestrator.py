"""Task orchestrator - main workflow coordination."""

import asyncio
import time
import uuid
from typing import Optional
from .types import Task, TaskResult, TaskStatus, PRState
from .git_manager import GitManager
from .process_manager import ProcessManager
from .client_manager import ClientManager
from .session_manager import SessionManager
from .pr_manager import PRManager


class TaskOrchestrator:
    """Orchestrates task execution workflow."""

    def __init__(
        self,
        git_manager: GitManager,
        process_manager: ProcessManager,
        client_manager: ClientManager,
        session_manager: SessionManager,
        pr_manager: PRManager,
    ):
        """Initialize task orchestrator.

        Args:
            git_manager: GitManager instance
            process_manager: ProcessManager instance
            client_manager: ClientManager instance
            session_manager: SessionManager instance
            pr_manager: PRManager instance
        """
        self.git_manager = git_manager
        self.process_manager = process_manager
        self.client_manager = client_manager
        self.session_manager = session_manager
        self.pr_manager = pr_manager

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute a task with full workflow.

        Workflow:
        1. Validate git repository
        2. Create branch
        3. Start OpenCode server
        4. Create session
        5. Send task prompt
        6. Wait for PR creation
        7. Poll PR status
        8. Handle feedback loop until merged or timeout
        9. Cleanup

        Args:
            task: Task to execute

        Returns:
            TaskResult
        """
        start_time = time.time()
        iterations = 0
        session_id = None
        server_pid = None

        try:
            # Step 1: Validate git repository
            if not await self.git_manager.is_git_repo(task.working_directory):
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error="Directory is not a git repository",
                    elapsed_time=time.time() - start_time,
                )

            # Step 2: Create branch
            original_branch = await self.git_manager.get_current_branch(task.working_directory)

            if await self.git_manager.branch_exists(task.working_directory, task.branch_name):
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error=f"Branch already exists: {task.branch_name}",
                    elapsed_time=time.time() - start_time,
                )

            await self.git_manager.create_branch(task.working_directory, task.branch_name)

            # Step 3: Start OpenCode server
            process_info = await self.process_manager.spawn_server(task.working_directory)
            server_pid = process_info.pid

            # Create client
            client = self.client_manager.create_client(process_info.port)

            # Step 4: Create session
            session_info = await self.session_manager.create_session(
                task_id=task.id,
                server_pid=process_info.pid,
                server_port=process_info.port,
                working_dir=task.working_directory,
                branch_name=task.branch_name,
            )
            session_id = session_info.session_id

            # Step 5: Send initial task prompt
            task_prompt = self._format_task_prompt(task.description, task.branch_name)
            await self.session_manager.send_prompt(session_id, task_prompt)

            # Step 6: Wait for PR creation
            pr_url, pr_number = await self._wait_for_pr_creation(
                session_id=session_id,
                working_dir=task.working_directory,
                timeout=task.timeout_minutes * 60,
            )

            if not pr_number:
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error="Agent did not create a PR within timeout",
                    iterations=iterations,
                    elapsed_time=time.time() - start_time,
                )

            # Update session with PR info
            self.session_manager.update_session(
                session_id,
                pr_url=pr_url,
                pr_number=pr_number,
                status=TaskStatus.PR_CREATED,
            )

            # Step 7-8: Poll PR and handle feedback
            result = await self._pr_feedback_loop(
                session_id=session_id,
                pr_number=pr_number,
                working_dir=task.working_directory,
                timeout=task.timeout_minutes * 60,
            )
            iterations = result.iterations

            # Step 9: Cleanup on success
            if result.status == TaskStatus.COMPLETED:
                # Delete the branch
                await self.git_manager.checkout_branch(task.working_directory, original_branch)
                await self.git_manager.delete_branch(task.working_directory, task.branch_name)

            result.elapsed_time = time.time() - start_time
            return result

        except Exception as e:
            # Cleanup on error
            if session_id:
                try:
                    await self.session_manager.delete_session(session_id)
                except Exception:
                    pass

            if server_pid:
                try:
                    await self.process_manager.kill_server(server_pid)
                except Exception:
                    pass

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=str(e),
                iterations=iterations,
                elapsed_time=time.time() - start_time,
            )

    def _format_task_prompt(self, description: str, branch_name: str) -> str:
        """Format the initial task prompt for the agent.

        Args:
            description: Task description
            branch_name: Branch name

        Returns:
            Formatted prompt
        """
        return f"""You are working on a new branch '{branch_name}' to complete the following task:

{description}

Please complete this task and create a pull request when you are done. Use the `gh pr create` command to create the PR with an appropriate title and description.

Important:
- Make sure all changes are committed before creating the PR
- Include clear commit messages
- Write a descriptive PR title and body
- The PR should be ready for review"""

    def _format_feedback_prompt(self, comments: list) -> str:
        """Format PR feedback prompt for the agent.

        Args:
            comments: List of PR comments

        Returns:
            Formatted prompt
        """
        formatted_comments = self.pr_manager.format_comments_for_agent(comments)

        return f"""Your pull request has received review comments. Please address the feedback and update the PR:

{formatted_comments}

Please:
1. Read and understand each comment
2. Make the necessary changes
3. Commit your changes
4. Push to update the PR

The PR will be automatically checked again after you push your changes."""

    async def _wait_for_pr_creation(
        self,
        session_id: str,
        working_dir: str,
        timeout: float,
        poll_interval: float = 10.0,
    ) -> tuple[Optional[str], Optional[int]]:
        """Wait for agent to create a PR.

        Args:
            session_id: Session ID
            working_dir: Working directory
            timeout: Timeout in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Tuple of (pr_url, pr_number) or (None, None) if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Get session messages
            messages = await self.session_manager.get_messages(session_id)

            # Check if PR was created
            pr_info = await self.pr_manager.get_pr_from_messages(messages, working_dir)
            if pr_info:
                return pr_info

            # Wait before next check
            await asyncio.sleep(poll_interval)

        return (None, None)

    async def _pr_feedback_loop(
        self,
        session_id: str,
        pr_number: int,
        working_dir: str,
        timeout: float,
        poll_interval: float = 30.0,
    ) -> TaskResult:
        """Poll PR status and handle feedback until merged or timeout.

        Args:
            session_id: Session ID
            pr_number: PR number
            working_dir: Working directory
            timeout: Timeout in seconds
            poll_interval: Polling interval in seconds

        Returns:
            TaskResult
        """
        start_time = time.time()
        iterations = 0
        session_info = self.session_manager.get_session(session_id)

        while time.time() - start_time < timeout:
            # Get PR status
            pr_status = await self.pr_manager.get_pr_status(pr_number, working_dir)

            # Check if merged
            if pr_status.state == PRState.MERGED:
                return TaskResult(
                    task_id=session_info.task_id,
                    status=TaskStatus.COMPLETED,
                    pr_url=pr_status.url,
                    pr_number=pr_number,
                    iterations=iterations,
                )

            # Check if closed (not merged)
            if pr_status.state == PRState.CLOSED:
                return TaskResult(
                    task_id=session_info.task_id,
                    status=TaskStatus.FAILED,
                    pr_url=pr_status.url,
                    pr_number=pr_number,
                    error="PR was closed without merging",
                    iterations=iterations,
                )

            # Check for new comments
            if pr_status.comments:
                iterations += 1

                # Send feedback to agent
                feedback_prompt = self._format_feedback_prompt(pr_status.comments)
                await self.session_manager.send_prompt(session_id, feedback_prompt)

                # Update session status
                self.session_manager.update_session(session_id, status=TaskStatus.AWAITING_REVIEW)

                # Wait a bit longer for agent to process feedback
                await asyncio.sleep(poll_interval * 2)
            else:
                # No comments, just wait
                await asyncio.sleep(poll_interval)

        # Timeout reached
        return TaskResult(
            task_id=session_info.task_id,
            status=TaskStatus.TIMEOUT,
            pr_url=pr_status.url if pr_status else None,
            pr_number=pr_number,
            error=f"Timeout waiting for PR merge ({timeout}s)",
            iterations=iterations,
        )
