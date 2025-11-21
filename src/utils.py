"""Utility functions for NomadMCP."""

import asyncio
import logging
from typing import Optional, Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[..., Any],
    *args,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> T:
    """Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch
        **kwargs: Keyword arguments for func

    Returns:
        Result from successful function call

    Raises:
        Last exception if all attempts fail
    """
    last_exception = None
    current_delay = delay

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt == max_attempts:
                logger.error(
                    f"Failed after {max_attempts} attempts: {func.__name__}",
                    exc_info=True,
                )
                raise

            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                f"Retrying in {current_delay}s..."
            )
            await asyncio.sleep(current_delay)
            current_delay *= backoff

    raise last_exception


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate a string to a maximum length.

    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - len(suffix)] + suffix


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1m 30s", "2h 15m")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours < 24:
        return f"{hours}h {remaining_minutes}m"

    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours}h"


def parse_github_url(url: str) -> Optional[tuple[str, str, int]]:
    """Parse GitHub PR URL to extract owner, repo, and PR number.

    Args:
        url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)

    Returns:
        Tuple of (owner, repo, pr_number) or None if invalid
    """
    import re

    pattern = r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(pattern, url)

    if match:
        owner, repo, pr_number = match.groups()
        return (owner, repo, int(pr_number))

    return None


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float,
    poll_interval: float = 1.0,
    timeout_message: str = "Timeout waiting for condition",
) -> bool:
    """Wait for a condition to become true.

    Args:
        condition: Callable that returns True when condition is met
        timeout: Timeout in seconds
        poll_interval: Polling interval in seconds
        timeout_message: Message to include in timeout exception

    Returns:
        True if condition met, False if timeout

    Raises:
        asyncio.TimeoutError: If timeout is reached
    """
    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < timeout:
        if condition():
            return True
        await asyncio.sleep(poll_interval)

    raise asyncio.TimeoutError(timeout_message)


def sanitize_branch_name(name: str) -> str:
    """Sanitize a string to be a valid git branch name.

    Args:
        name: Branch name to sanitize

    Returns:
        Sanitized branch name
    """
    import re

    # Replace invalid characters with hyphens
    name = re.sub(r"[^a-zA-Z0-9/_-]", "-", name)

    # Remove leading/trailing hyphens and slashes
    name = name.strip("-/")

    # Collapse multiple hyphens
    name = re.sub(r"-+", "-", name)

    # Ensure it doesn't end with .lock
    if name.endswith(".lock"):
        name = name[:-5]

    # Limit length
    max_length = 255
    if len(name) > max_length:
        name = name[:max_length].rstrip("-/")

    return name or "task"


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            calls_per_minute: Maximum calls per minute
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time: Optional[float] = None

    async def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        if self.last_call_time is None:
            self.last_call_time = asyncio.get_event_loop().time()
            return

        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - self.last_call_time
        wait_time = self.min_interval - elapsed

        if wait_time > 0:
            await asyncio.sleep(wait_time)

        self.last_call_time = asyncio.get_event_loop().time()
