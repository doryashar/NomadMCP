"""Tests for utility functions."""

import pytest
import asyncio

from src.utils import (
    truncate_string,
    format_duration,
    parse_github_url,
    sanitize_branch_name,
    retry_async,
)


def test_truncate_string():
    """Test string truncation."""
    # Short string - no truncation
    assert truncate_string("hello", 10) == "hello"

    # Long string - truncation
    assert truncate_string("hello world", 8) == "hello..."

    # Custom suffix
    assert truncate_string("hello world", 8, "..") == "hello.."


def test_format_duration():
    """Test duration formatting."""
    assert format_duration(30) == "30.0s"
    assert format_duration(90) == "1m 30s"
    assert format_duration(3661) == "1h 1m"
    assert format_duration(90000) == "1d 1h"


def test_parse_github_url():
    """Test GitHub URL parsing."""
    # Valid URL
    result = parse_github_url("https://github.com/owner/repo/pull/123")
    assert result == ("owner", "repo", 123)

    # Valid URL with http
    result = parse_github_url("http://github.com/owner/repo/pull/456")
    assert result == ("owner", "repo", 456)

    # Invalid URL
    result = parse_github_url("https://gitlab.com/owner/repo/merge_requests/123")
    assert result is None

    # Invalid format
    result = parse_github_url("not a url")
    assert result is None


def test_sanitize_branch_name():
    """Test branch name sanitization."""
    # Basic sanitization
    assert sanitize_branch_name("feature/my-feature") == "feature/my-feature"

    # Remove invalid characters
    assert sanitize_branch_name("feature@#$%test") == "feature----test"

    # Collapse multiple hyphens
    assert sanitize_branch_name("feature---test") == "feature-test"

    # Remove leading/trailing hyphens
    assert sanitize_branch_name("-feature-") == "feature"

    # Handle .lock suffix
    assert sanitize_branch_name("feature.lock") == "feature"

    # Empty result defaults to "task"
    assert sanitize_branch_name("@#$%") == "task"


@pytest.mark.asyncio
async def test_retry_async_success():
    """Test retry with successful call."""
    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await retry_async(func, max_attempts=3, delay=0.1)
    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_async_eventual_success():
    """Test retry with eventual success."""
    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Not yet")
        return "success"

    result = await retry_async(func, max_attempts=3, delay=0.1, backoff=1.0)
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_async_failure():
    """Test retry with all attempts failing."""
    call_count = 0

    async def func():
        nonlocal call_count
        call_count += 1
        raise ValueError("Always fails")

    with pytest.raises(ValueError, match="Always fails"):
        await retry_async(func, max_attempts=3, delay=0.1, backoff=1.0)

    assert call_count == 3
