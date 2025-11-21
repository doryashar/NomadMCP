"""Tests for GitManager."""

import pytest
import tempfile
import shutil
from pathlib import Path
import git

from src.git_manager import GitManager


@pytest.fixture
def temp_repo():
    """Create a temporary git repository."""
    temp_dir = tempfile.mkdtemp()
    repo = git.Repo.init(temp_dir)

    # Create initial commit
    test_file = Path(temp_dir) / "README.md"
    test_file.write_text("# Test Repository")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_is_git_repo(temp_repo):
    """Test git repository validation."""
    manager = GitManager()

    # Should be a valid repo
    assert await manager.is_git_repo(temp_repo)

    # Should not be a valid repo
    with tempfile.TemporaryDirectory() as temp_dir:
        assert not await manager.is_git_repo(temp_dir)


@pytest.mark.asyncio
async def test_get_current_branch(temp_repo):
    """Test getting current branch."""
    manager = GitManager()

    branch = await manager.get_current_branch(temp_repo)
    assert branch in ["main", "master"]  # Could be either


@pytest.mark.asyncio
async def test_create_branch(temp_repo):
    """Test branch creation."""
    manager = GitManager()

    # Create new branch
    await manager.create_branch(temp_repo, "feature/test")

    # Verify branch exists
    assert await manager.branch_exists(temp_repo, "feature/test")

    # Verify we're on the new branch
    current = await manager.get_current_branch(temp_repo)
    assert current == "feature/test"


@pytest.mark.asyncio
async def test_create_branch_already_exists(temp_repo):
    """Test creating a branch that already exists."""
    manager = GitManager()

    # Create branch
    await manager.create_branch(temp_repo, "feature/test")

    # Try to create again - should fail
    with pytest.raises(ValueError, match="Branch already exists"):
        await manager.create_branch(temp_repo, "feature/test")


@pytest.mark.asyncio
async def test_delete_branch(temp_repo):
    """Test branch deletion."""
    manager = GitManager()

    # Create and switch to new branch
    await manager.create_branch(temp_repo, "feature/test")

    # Switch back to main
    original_branch = "main" if await manager.branch_exists(temp_repo, "main") else "master"
    await manager.checkout_branch(temp_repo, original_branch)

    # Delete branch
    await manager.delete_branch(temp_repo, "feature/test")

    # Verify branch is gone
    assert not await manager.branch_exists(temp_repo, "feature/test")


@pytest.mark.asyncio
async def test_cannot_delete_current_branch(temp_repo):
    """Test that we cannot delete the current branch."""
    manager = GitManager()

    current_branch = await manager.get_current_branch(temp_repo)

    with pytest.raises(ValueError, match="Cannot delete current branch"):
        await manager.delete_branch(temp_repo, current_branch)
