"""Git repository operations manager."""

import os
from pathlib import Path
from typing import Optional
import git
from git.exc import GitCommandError, InvalidGitRepositoryError


class GitManager:
    """Manages git operations for task branches."""

    @staticmethod
    async def is_git_repo(directory: str) -> bool:
        """Check if directory is a git repository.

        Args:
            directory: Path to check

        Returns:
            True if directory is a git repository
        """
        try:
            git.Repo(directory, search_parent_directories=False)
            return True
        except InvalidGitRepositoryError:
            return False

    @staticmethod
    async def get_repo(directory: str) -> git.Repo:
        """Get git repository object.

        Args:
            directory: Path to repository

        Returns:
            Git repository object

        Raises:
            ValueError: If directory is not a git repository
        """
        try:
            return git.Repo(directory, search_parent_directories=False)
        except InvalidGitRepositoryError:
            raise ValueError(f"Directory is not a git repository: {directory}")

    @staticmethod
    async def get_current_branch(directory: str) -> str:
        """Get current branch name.

        Args:
            directory: Path to repository

        Returns:
            Current branch name
        """
        repo = await GitManager.get_repo(directory)
        return repo.active_branch.name

    @staticmethod
    async def create_branch(directory: str, branch_name: str, from_branch: Optional[str] = None) -> None:
        """Create a new branch.

        Args:
            directory: Path to repository
            branch_name: Name of new branch
            from_branch: Base branch (defaults to current branch)

        Raises:
            ValueError: If branch already exists
        """
        repo = await GitManager.get_repo(directory)

        # Check if branch already exists
        if branch_name in repo.heads:
            raise ValueError(f"Branch already exists: {branch_name}")

        # Get base commit
        if from_branch:
            if from_branch not in repo.heads:
                raise ValueError(f"Base branch not found: {from_branch}")
            base_commit = repo.heads[from_branch].commit
        else:
            base_commit = repo.head.commit

        # Create and checkout new branch
        new_branch = repo.create_head(branch_name, base_commit)
        new_branch.checkout()

    @staticmethod
    async def delete_branch(directory: str, branch_name: str, force: bool = False) -> None:
        """Delete a branch.

        Args:
            directory: Path to repository
            branch_name: Name of branch to delete
            force: Force delete even if not merged

        Raises:
            ValueError: If branch doesn't exist or is current branch
        """
        repo = await GitManager.get_repo(directory)

        # Check if branch exists
        if branch_name not in repo.heads:
            raise ValueError(f"Branch not found: {branch_name}")

        # Can't delete current branch
        if repo.active_branch.name == branch_name:
            raise ValueError(f"Cannot delete current branch: {branch_name}")

        # Delete branch
        repo.delete_head(branch_name, force=force)

    @staticmethod
    async def checkout_branch(directory: str, branch_name: str) -> None:
        """Checkout a branch.

        Args:
            directory: Path to repository
            branch_name: Name of branch to checkout

        Raises:
            ValueError: If branch doesn't exist
        """
        repo = await GitManager.get_repo(directory)

        if branch_name not in repo.heads:
            raise ValueError(f"Branch not found: {branch_name}")

        repo.heads[branch_name].checkout()

    @staticmethod
    async def get_remote_url(directory: str, remote: str = "origin") -> Optional[str]:
        """Get remote URL.

        Args:
            directory: Path to repository
            remote: Remote name (default: origin)

        Returns:
            Remote URL or None if not found
        """
        repo = await GitManager.get_repo(directory)

        try:
            return repo.remote(remote).url
        except ValueError:
            return None

    @staticmethod
    async def branch_exists(directory: str, branch_name: str) -> bool:
        """Check if branch exists.

        Args:
            directory: Path to repository
            branch_name: Branch name to check

        Returns:
            True if branch exists
        """
        repo = await GitManager.get_repo(directory)
        return branch_name in repo.heads

    @staticmethod
    async def create_worktree(
        directory: str,
        branch_name: str,
        worktree_path: str,
        from_branch: Optional[str] = None,
    ) -> str:
        """Create a git worktree for parallel work.

        Args:
            directory: Path to main repository
            branch_name: Name of new branch for worktree
            worktree_path: Path where worktree will be created
            from_branch: Base branch (defaults to current branch)

        Returns:
            Path to created worktree

        Raises:
            ValueError: If worktree creation fails
        """
        import subprocess

        repo = await GitManager.get_repo(directory)

        # Build worktree command
        cmd = ["git", "worktree", "add"]

        if from_branch:
            cmd.extend(["-b", branch_name, worktree_path, from_branch])
        else:
            cmd.extend(["-b", branch_name, worktree_path])

        try:
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
            )
            return worktree_path
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to create worktree: {e.stderr}")

    @staticmethod
    async def remove_worktree(directory: str, worktree_path: str, force: bool = False) -> None:
        """Remove a git worktree.

        Args:
            directory: Path to main repository
            worktree_path: Path to worktree to remove
            force: Force removal even with uncommitted changes

        Raises:
            ValueError: If worktree removal fails
        """
        import subprocess

        cmd = ["git", "worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(worktree_path)

        try:
            subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to remove worktree: {e.stderr}")

    @staticmethod
    async def list_worktrees(directory: str) -> list[dict]:
        """List all worktrees for a repository.

        Args:
            directory: Path to repository

        Returns:
            List of worktree info dicts with 'path', 'branch', 'commit'
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
            )

            worktrees = []
            current = {}

            for line in result.stdout.strip().split("\n"):
                if not line:
                    if current:
                        worktrees.append(current)
                        current = {}
                    continue

                if line.startswith("worktree "):
                    current["path"] = line.split(" ", 1)[1]
                elif line.startswith("branch "):
                    current["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
                elif line.startswith("HEAD "):
                    current["commit"] = line.split(" ", 1)[1]

            if current:
                worktrees.append(current)

            return worktrees
        except subprocess.CalledProcessError:
            return []

    @staticmethod
    async def worktree_exists(directory: str, worktree_path: str) -> bool:
        """Check if a worktree exists.

        Args:
            directory: Path to repository
            worktree_path: Path to check

        Returns:
            True if worktree exists
        """
        worktrees = await GitManager.list_worktrees(directory)
        return any(wt["path"] == worktree_path for wt in worktrees)
