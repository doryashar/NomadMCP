"""OpenCode HTTP API client manager."""

import httpx
from typing import Any, Optional


class OpenCodeClient:
    """HTTP client for OpenCode API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        """Initialize OpenCode client.

        Args:
            base_url: Base URL for OpenCode server (e.g., http://localhost:8080)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Any:
        """Make an HTTP request.

        Args:
            method: HTTP method
            path: API path
            json: JSON body
            params: Query parameters

        Returns:
            Response data

        Raises:
            httpx.HTTPError: On HTTP errors
        """
        url = f"{self.base_url}{path}"
        try:
            response = await self.client.request(method, url, json=json, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # Include response body in error for debugging
            if hasattr(e, "response") and e.response:
                error_detail = e.response.text
                raise RuntimeError(f"HTTP {e.response.status_code}: {error_detail}") from e
            raise
        except httpx.HTTPError as e:
            # Include response body in error for debugging
            if hasattr(e, "response") and e.response:
                error_detail = e.response.text
                raise RuntimeError(f"HTTP {e.response.status_code}: {error_detail}") from e
            raise

    # Session API
    async def list_sessions(self) -> list[dict]:
        """List all sessions.

        Returns:
            List of session objects
        """
        return await self._request("GET", "/session")

    async def create_session(self) -> dict:
        """Create a new session.

        Returns:
            Session object with id, title, etc.
        """
        return await self._request("POST", "/session")

    async def delete_session(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: Session ID to delete
        """
        await self._request("DELETE", f"/session/{session_id}")

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get messages for a session.

        Args:
            session_id: Session ID

        Returns:
            List of message objects
        """
        return await self._request("GET", f"/session/{session_id}/message")

    async def send_prompt(
        self,
        session_id: str,
        prompt: str,
        message_id: str,
        agent: Optional[str] = None,
        model: Optional[dict] = None,
    ) -> dict:
        """Send a prompt to a session.

        Args:
            session_id: Session ID
            prompt: Prompt text
            message_id: Unique message ID
            agent: Agent name (optional)
            model: Model config with providerID and modelID (optional)

        Returns:
            Response data
        """
        body = {
            "messageID": message_id,
            "parts": [{"type": "text", "text": prompt}],
        }

        if agent:
            body["agent"] = agent

        if model:
            body["model"] = model

        response = await self._request("POST", f"/session/{session_id}/message", json=body)
        return response

    async def init_session(
        self,
        session_id: str,
        message_id: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> None:
        """Initialize a session by analyzing the project.

        Args:
            session_id: Session ID
            message_id: Message ID for the init request
            provider_id: Provider ID (optional)
            model_id: Model ID (optional)
        """
        body = {"messageID": message_id}
        if provider_id:
            body["providerID"] = provider_id
        if model_id:
            body["modelID"] = model_id

        await self._request("POST", f"/session/{session_id}/init", json=body)

    async def abort_session(self, session_id: str) -> None:
        """Abort a running session.

        Args:
            session_id: Session ID to abort
        """
        await self._request("POST", f"/session/{session_id}/abort")

    # Config API
    async def get_providers(self) -> dict:
        """Get available providers and models.

        Returns:
            Providers configuration
        """
        response = await self._request("GET", "/config.providers")
        return response.get("data", {})

    # App API
    async def get_agents(self) -> list[dict]:
        """Get available agents.

        Returns:
            List of agent objects
        """
        response = await self._request("GET", "/app.agents")
        return response.get("data", [])


class ClientManager:
    """Manages OpenCode HTTP clients."""

    def __init__(self):
        """Initialize client manager."""
        self.clients: dict[int, OpenCodeClient] = {}

    def create_client(self, port: int, timeout: float = 30.0) -> OpenCodeClient:
        """Create or get a client for a port.

        Args:
            port: Port number
            timeout: Request timeout in seconds

        Returns:
            OpenCodeClient instance
        """
        if port in self.clients:
            return self.clients[port]

        client = OpenCodeClient(f"http://localhost:{port}", timeout=timeout)
        self.clients[port] = client
        return client

    def get_client(self, port: int) -> Optional[OpenCodeClient]:
        """Get client for a port.

        Args:
            port: Port number

        Returns:
            OpenCodeClient or None if not found
        """
        return self.clients.get(port)

    async def destroy_client(self, port: int) -> None:
        """Destroy client for a port.

        Args:
            port: Port number
        """
        client = self.clients.get(port)
        if client:
            await client.close()
            del self.clients[port]

    async def destroy_all(self) -> None:
        """Destroy all clients."""
        ports = list(self.clients.keys())
        for port in ports:
            await self.destroy_client(port)
