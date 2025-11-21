"""Task queue manager for parallel execution control."""

import asyncio
from typing import Optional, Dict, Set
from datetime import datetime
from .types import Task, TaskResult, TaskStatus
from .task_orchestrator import TaskOrchestrator
from .logging_config import get_logger

logger = get_logger(__name__)


class TaskQueue:
    """Manages task execution with parallel limits and tracking."""

    def __init__(self, orchestrator: TaskOrchestrator, max_parallel: int = 5):
        """Initialize task queue.

        Args:
            orchestrator: TaskOrchestrator instance
            max_parallel: Maximum number of parallel tasks
        """
        self.orchestrator = orchestrator
        self.max_parallel = max_parallel
        self.semaphore = asyncio.Semaphore(max_parallel)

        # Track active tasks (protected by lock)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self.task_start_times: Dict[str, datetime] = {}

        # Track tasks per directory (for worktree coordination)
        self.tasks_per_directory: Dict[str, Set[str]] = {}

        # Lock for thread-safe dictionary access
        self._lock = asyncio.Lock()

    async def submit_task(self, task: Task) -> str:
        """Submit a task for execution.

        Args:
            task: Task to execute

        Returns:
            Task ID
        """
        logger.info(f"Submitting task {task.id} to queue")

        async with self._lock:
            logger.debug(f"Current active tasks: {len(self.active_tasks)}/{self.max_parallel}")

            # Track directory usage
            if task.working_directory not in self.tasks_per_directory:
                self.tasks_per_directory[task.working_directory] = set()
            self.tasks_per_directory[task.working_directory].add(task.id)

            # Create async task
            async_task = asyncio.create_task(self._execute_task(task))
            self.active_tasks[task.id] = async_task
            self.task_start_times[task.id] = datetime.now()

        return task.id

    async def _execute_task(self, task: Task) -> TaskResult:
        """Execute a task with semaphore control.

        Args:
            task: Task to execute

        Returns:
            TaskResult
        """
        async with self.semaphore:
            logger.info(f"Starting execution of task {task.id}")
            try:
                result = await self.orchestrator.execute_task(task)
                async with self._lock:
                    self.task_results[task.id] = result
                logger.info(f"Task {task.id} completed with status: {result.status}")
                return result
            except Exception as e:
                logger.error(f"Task {task.id} failed with exception: {e}", exc_info=True)
                result = TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error=str(e),
                )
                async with self._lock:
                    self.task_results[task.id] = result
                return result
            finally:
                # Cleanup with lock protection
                async with self._lock:
                    if task.id in self.active_tasks:
                        del self.active_tasks[task.id]
                    if task.id in self.task_start_times:
                        del self.task_start_times[task.id]

                    # Remove from directory tracking
                    if task.working_directory in self.tasks_per_directory:
                        self.tasks_per_directory[task.working_directory].discard(task.id)
                        if not self.tasks_per_directory[task.working_directory]:
                            del self.tasks_per_directory[task.working_directory]

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get result for a task.

        Args:
            task_id: Task ID

        Returns:
            TaskResult if available, None if still running
        """
        async with self._lock:
            if task_id in self.task_results:
                return self.task_results[task_id]

            if task_id in self.active_tasks:
                # Task still running
                return None

            # Task not found
            raise ValueError(f"Task {task_id} not found")

    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """Wait for a task to complete.

        Args:
            task_id: Task ID
            timeout: Optional timeout in seconds

        Returns:
            TaskResult

        Raises:
            asyncio.TimeoutError: If timeout is reached
            ValueError: If task not found
        """
        # Get task reference with lock
        async with self._lock:
            if task_id not in self.active_tasks:
                # Check if already completed
                if task_id in self.task_results:
                    return self.task_results[task_id]
                raise ValueError(f"Task {task_id} not found")
            task_ref = self.active_tasks[task_id]

        # Wait without holding lock
        if timeout:
            await asyncio.wait_for(task_ref, timeout=timeout)
        else:
            await task_ref

        # Get result with lock
        async with self._lock:
            return self.task_results[task_id]

    async def get_active_task_count(self) -> int:
        """Get number of active tasks.

        Returns:
            Number of active tasks
        """
        async with self._lock:
            return len(self.active_tasks)

    async def get_directory_task_count(self, directory: str) -> int:
        """Get number of active tasks for a directory.

        Args:
            directory: Directory path

        Returns:
            Number of active tasks for directory
        """
        async with self._lock:
            return len(self.tasks_per_directory.get(directory, set()))

    async def get_status(self) -> dict:
        """Get queue status.

        Returns:
            Status dictionary with active tasks, results, etc.
        """
        async with self._lock:
            return {
                "max_parallel": self.max_parallel,
                "active_tasks": len(self.active_tasks),
                "completed_tasks": len(self.task_results),
                "tasks_by_directory": {
                    dir: len(tasks) for dir, tasks in self.tasks_per_directory.items()
                },
                "active_task_ids": list(self.active_tasks.keys()),
            }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled, False if not found or already completed
        """
        async with self._lock:
            if task_id not in self.active_tasks:
                return False

            logger.info(f"Cancelling task {task_id}")
            task_ref = self.active_tasks[task_id]
            task_ref.cancel()

        try:
            await task_ref
        except asyncio.CancelledError:
            logger.info(f"Task {task_id} cancelled successfully")

        return True

    async def cancel_all(self) -> None:
        """Cancel all running tasks."""
        async with self._lock:
            active_count = len(self.active_tasks)
            task_ids = list(self.active_tasks.keys())

        logger.info(f"Cancelling all {active_count} active tasks")

        for task_id in task_ids:
            await self.cancel_task(task_id)
