"""GitHub Pull Request manager."""

import asyncio
import json
import re
from typing import Optional
from .types import PRStatus, PRComment, PRState


class PRManager:
    """Manages GitHub pull requests via gh CLI."""

    @staticmethod
    async def _run_gh_command(*args: str, cwd: str) -> str:
        """Run a gh command.

        Args:
            *args: Command arguments
            cwd: Working directory

        Returns:
            Command output

        Raises:
            RuntimeError: If command fails
        """
        cmd = ["gh", *args]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            raise RuntimeError(f"gh command failed: {error_msg}")

        return stdout.decode().strip()

    @staticmethod
    async def get_pr_from_messages(messages: list, working_dir: str) -> Optional[tuple[str, int]]:
        """Extract PR URL and number from session messages.

        Args:
            messages: List of session messages
            working_dir: Working directory

        Returns:
            Tuple of (pr_url, pr_number) or None if not found
        """
        # Look for gh pr create output in messages
        pr_url_pattern = re.compile(r"https://github\.com/[^/]+/[^/]+/pull/(\d+)")

        for message in reversed(messages):  # Check recent messages first
            for part in message.parts:
                if part.get("type") == "text":
                    text = part.get("text", "")
                    match = pr_url_pattern.search(text)
                    if match:
                        pr_number = int(match.group(1))
                        pr_url = match.group(0)
                        return (pr_url, pr_number)

        return None

    @staticmethod
    async def get_pr_status(pr_number: int, working_dir: str) -> PRStatus:
        """Get pull request status.

        Args:
            pr_number: PR number
            working_dir: Working directory

        Returns:
            PRStatus object

        Raises:
            RuntimeError: If gh command fails
        """
        # Get PR details as JSON
        output = await PRManager._run_gh_command(
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,title,url,state,mergeable,merged",
            cwd=working_dir,
        )

        # Validate output
        if not output or not output.strip():
            raise RuntimeError(f"Empty response from gh pr view for PR #{pr_number}")

        # Parse JSON with error handling
        try:
            pr_data = json.loads(output)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse PR data: {e}. Output was: {output[:100]}")

        # Get PR comments
        comments = await PRManager.get_pr_comments(pr_number, working_dir)

        # Map state
        state_str = pr_data.get("state", "OPEN").upper()
        if pr_data.get("merged"):
            state = PRState.MERGED
        elif state_str == "CLOSED":
            state = PRState.CLOSED
        else:
            state = PRState.OPEN

        return PRStatus(
            number=pr_data["number"],
            state=state,
            title=pr_data["title"],
            url=pr_data["url"],
            mergeable=pr_data.get("mergeable", "UNKNOWN") == "MERGEABLE",
            merged=pr_data.get("merged", False),
            comments=comments,
        )

    @staticmethod
    async def get_pr_comments(pr_number: int, working_dir: str) -> list[PRComment]:
        """Get PR comments and review feedback.

        Args:
            pr_number: PR number
            working_dir: Working directory

        Returns:
            List of PRComment objects
        """
        comments = []

        try:
            # Get PR comments
            output = await PRManager._run_gh_command(
                "pr",
                "view",
                str(pr_number),
                "--json",
                "comments",
                cwd=working_dir,
            )

            # Only parse if output is not empty
            if output and output.strip():
                data = json.loads(output)
                for comment in data.get("comments", []):
                    comments.append(
                        PRComment(
                            author=comment.get("author", {}).get("login", "unknown"),
                            body=comment.get("body", ""),
                            created_at=comment.get("createdAt", ""),
                        )
                    )
        except json.JSONDecodeError:
            pass  # Best effort - skip if JSON is malformed
        except Exception:
            pass  # Best effort - skip on any other error

        try:
            # Get review comments
            output = await PRManager._run_gh_command(
                "api",
                f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
                cwd=working_dir,
            )

            # Only parse if output is not empty
            if output and output.strip():
                review_comments = json.loads(output)
                for comment in review_comments:
                    comments.append(
                        PRComment(
                            author=comment.get("user", {}).get("login", "unknown"),
                            body=comment.get("body", ""),
                            path=comment.get("path"),
                            line=comment.get("line"),
                            created_at=comment.get("created_at", ""),
                        )
                    )
        except json.JSONDecodeError:
            pass  # Best effort - skip if JSON is malformed
        except Exception:
            pass  # Best effort - skip on any other error

        return comments

    @staticmethod
    async def close_pr(pr_number: int, working_dir: str) -> None:
        """Close a pull request.

        Args:
            pr_number: PR number
            working_dir: Working directory

        Raises:
            RuntimeError: If gh command fails
        """
        await PRManager._run_gh_command(
            "pr",
            "close",
            str(pr_number),
            cwd=working_dir,
        )

    @staticmethod
    def format_comments_for_agent(comments: list[PRComment]) -> str:
        """Format PR comments for sending to agent.

        Args:
            comments: List of PR comments

        Returns:
            Formatted string
        """
        if not comments:
            return "No comments found."

        parts = []
        for i, comment in enumerate(comments, 1):
            parts.append(f"Comment {i} from {comment.author}:")
            if comment.path and comment.line:
                parts.append(f"  File: {comment.path}:{comment.line}")
            parts.append(f"  {comment.body}")
            parts.append("")

        return "\n".join(parts)
