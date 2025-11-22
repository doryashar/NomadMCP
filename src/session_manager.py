"""OpenCode session manager."""

import time
import uuid
from typing import Optional
from .types import SessionInfo, TaskStatus, Message
from .client_manager import ClientManager


class SessionManager:
    """Manages OpenCode sessions."""

    def __init__(self, client_manager: ClientManager):
        """Initialize session manager.

        Args:
            client_manager: ClientManager instance
        """
        self.client_manager = client_manager
        self.sessions: dict[str, SessionInfo] = {}

    def _generate_message_id(self) -> str:
        """Generate a unique message ID.

        Returns:
            Message ID in format msg_<hex><random>
        """
        timestamp = int(time.time() * 1000)
        random_part = uuid.uuid4().hex[:14]
        hex_time = format(timestamp, "012x")
        return f"msg_{hex_time}{random_part}"

    async def create_session(
        self,
        task_id: str,
        server_pid: int,
        server_port: int,
        working_dir: str,
        branch_name: str,
    ) -> SessionInfo:
        """Create a new OpenCode session.

        Args:
            task_id: Task ID
            server_pid: Server process ID
            server_port: Server port
            working_dir: Working directory
            branch_name: Git branch name

        Returns:
            SessionInfo

        Raises:
            RuntimeError: If session creation fails
        """
        client = self.client_manager.get_client(server_port)
        if not client:
            raise RuntimeError(f"No client found for port {server_port}")

        # Create session via API
        session_data = await client.create_session()
        session_id = session_data.get("id")

        if not session_id:
            raise RuntimeError("Failed to create session: No session ID returned")

        # Create session info
        now = time.time()
        session_info = SessionInfo(
            session_id=session_id,
            task_id=task_id,
            instance_id=str(server_port),  # Use port as instance ID
            server_pid=server_pid,
            server_port=server_port,
            branch_name=branch_name,
            status=TaskStatus.IN_PROGRESS,
            created_at=now,
            updated_at=now,
        )

        self.sessions[session_id] = session_info
        return session_info

    async def init_session(
        self,
        session_id: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> None:
        """Initialize a session.

        Args:
            session_id: Session ID
            provider_id: Provider ID (optional)
            model_id: Model ID (optional)

        Raises:
            ValueError: If session not found
            RuntimeError: If init fails
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        client = self.client_manager.get_client(session.server_port)
        if not client:
            raise RuntimeError(f"No client found for session {session_id}")

        # Generate message ID
        message_id = self._generate_message_id()

        # Init session
        await client.init_session(
            session_id=session_id,
            message_id=message_id,
            provider_id=provider_id,
            model_id=model_id,
        )

        # Update session timestamp
        session.updated_at = time.time()

    async def send_prompt(
        self,
        session_id: str,
        prompt: str,
        agent: Optional[str] = None,
    ) -> None:
        """Send a prompt to a session.

        Args:
            session_id: Session ID
            prompt: Prompt text
            agent: Agent name (optional)

        Raises:
            ValueError: If session not found
            RuntimeError: If prompt fails to send
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        client = self.client_manager.get_client(session.server_port)
        if not client:
            raise RuntimeError(f"No client found for session {session_id}")

        # Generate message ID
        message_id = self._generate_message_id()

        # Send prompt
        await client.send_prompt(
            session_id=session_id,
            prompt=prompt,
            message_id=message_id,
            agent=agent,
        )

        # Update session timestamp
        session.updated_at = time.time()

    async def get_messages(self, session_id: str) -> list[Message]:
        """Get messages from a session.

        Args:
            session_id: Session ID

        Returns:
            List of messages

        Raises:
            ValueError: If session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        client = self.client_manager.get_client(session.server_port)
        if not client:
            raise RuntimeError(f"No client found for session {session_id}")

        # Get messages from API
        messages_data = await client.get_messages(session_id)

        # Convert to Message objects
        messages = []
        for msg_data in messages_data:
            info = msg_data.get("info", msg_data)
            messages.append(
                Message(
                    id=info.get("id", ""),
                    role=info.get("role", "assistant"),
                    parts=msg_data.get("parts", []),
                    timestamp=info.get("time", {}).get("created", time.time()),
                )
            )

        return messages

    async def abort_session(self, session_id: str) -> None:
        """Abort a running session.

        Args:
            session_id: Session ID

        Raises:
            ValueError: If session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        client = self.client_manager.get_client(session.server_port)
        if not client:
            return  # Client already destroyed

        try:
            await client.abort_session(session_id)
        except Exception:
            pass  # Best effort

    async def delete_session(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: Session ID

        Raises:
            ValueError: If session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return  # Already deleted

        client = self.client_manager.get_client(session.server_port)
        if client:
            try:
                await client.delete_session(session_id)
            except Exception:
                pass  # Best effort

        # Remove from tracking
        del self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session info.

        Args:
            session_id: Session ID

        Returns:
            SessionInfo or None if not found
        """
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, **kwargs) -> None:
        """Update session info.

        Args:
            session_id: Session ID
            **kwargs: Fields to update
        """
        session = self.sessions.get(session_id)
        if session:
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            session.updated_at = time.time()

    async def cleanup_all(self) -> None:
        """Clean up all sessions."""
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.delete_session(session_id)
