"""OpenCode server process manager."""

import asyncio
import os
import re
import signal
import time
from typing import Optional
import subprocess
from .types import ProcessInfo


class ProcessManager:
    """Manages OpenCode server processes."""

    def __init__(self):
        """Initialize process manager."""
        self.processes: dict[int, ProcessInfo] = {}

    async def spawn_server(
        self,
        working_dir: str,
        binary_path: str = "opencode",
        timeout: float = 10.0,
    ) -> ProcessInfo:
        """Spawn an OpenCode server process.

        Args:
            working_dir: Working directory for the server
            binary_path: Path to opencode binary (default: "opencode")
            timeout: Timeout in seconds to wait for server to start

        Returns:
            ProcessInfo with server details

        Raises:
            RuntimeError: If server fails to start
            FileNotFoundError: If binary not found
        """
        # Validate working directory
        if not os.path.isdir(working_dir):
            raise ValueError(f"Working directory not found: {working_dir}")

        # Build command
        cmd = [binary_path, "serve", "--port", "0", "--print-logs", "--log-level", "DEBUG"]

        # Spawn process
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"OpenCode binary not found: {binary_path}. "
                "Please install OpenCode CLI: npm install -g @opencode/cli"
            )

        # Wait for server to start and extract port
        port = await self._wait_for_server_start(process, timeout)

        # Store process info
        process_info = ProcessInfo(
            pid=process.pid,
            port=port,
            working_dir=working_dir,
            started_at=time.time(),
        )
        self.processes[process.pid] = process_info

        return process_info

    async def _wait_for_server_start(
        self,
        process: asyncio.subprocess.Process,
        timeout: float,
    ) -> int:
        """Wait for server to start and extract port from output.

        Args:
            process: Subprocess object
            timeout: Timeout in seconds

        Returns:
            Port number the server is listening on

        Raises:
            RuntimeError: If server fails to start or timeout reached
        """
        start_time = time.time()
        port_pattern = re.compile(r"opencode server listening on http://[^:]+:(\d+)")

        while time.time() - start_time < timeout:
            # Check if process has terminated
            if process.returncode is not None:
                stderr = await process.stderr.read()
                # Close streams before raising
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
                raise RuntimeError(f"OpenCode server failed to start: {stderr.decode()}")

            # Try to read a line from stdout
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=0.5)
                if not line:
                    continue

                line_str = line.decode().strip()
                match = port_pattern.search(line_str)
                if match:
                    return int(match.group(1))
            except asyncio.TimeoutError:
                continue

        # Timeout reached - cleanup process properly
        process.kill()
        try:
            # Wait for process to actually die (max 2 seconds)
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            # Process still alive after SIGKILL, something is very wrong
            pass
        finally:
            # Close streams to free resources
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

        raise RuntimeError(f"Timeout waiting for OpenCode server to start ({timeout}s)")

    async def kill_server(self, pid: int) -> None:
        """Kill an OpenCode server process.

        Args:
            pid: Process ID to kill
        """
        if pid not in self.processes:
            return

        try:
            os.kill(pid, signal.SIGTERM)
            # Wait a bit for graceful shutdown
            await asyncio.sleep(2)
            # Force kill if still running
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Already dead
        except ProcessLookupError:
            pass  # Process already terminated

        # Remove from tracking
        del self.processes[pid]

    async def is_running(self, pid: int) -> bool:
        """Check if a process is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running
        """
        if pid not in self.processes:
            return False

        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """Get process information.

        Args:
            pid: Process ID

        Returns:
            ProcessInfo or None if not found
        """
        return self.processes.get(pid)

    async def cleanup_all(self) -> None:
        """Kill all managed processes."""
        pids = list(self.processes.keys())
        for pid in pids:
            await self.kill_server(pid)
