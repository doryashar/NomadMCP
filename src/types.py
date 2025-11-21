"""Data models and types for NomadMCP."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PR_CREATED = "pr_created"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class PRState(str, Enum):
    """Pull request state."""

    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class ProcessInfo(BaseModel):
    """Information about a running OpenCode server process."""

    pid: int
    port: int
    working_dir: str
    started_at: float


class Task(BaseModel):
    """Task to be executed."""

    id: str
    description: str
    working_directory: str
    branch_name: str
    timeout_minutes: int = Field(default=60)


class SessionInfo(BaseModel):
    """Information about an OpenCode session."""

    session_id: str
    task_id: str
    instance_id: str
    server_pid: int
    server_port: int
    branch_name: str
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    status: TaskStatus
    created_at: float
    updated_at: float


class PRComment(BaseModel):
    """Pull request comment or review feedback."""

    author: str
    body: str
    path: Optional[str] = None
    line: Optional[int] = None
    created_at: str


class PRStatus(BaseModel):
    """Pull request status information."""

    number: int
    state: PRState
    title: str
    url: str
    mergeable: bool
    merged: bool
    comments: list[PRComment] = Field(default_factory=list)


class TaskResult(BaseModel):
    """Result of task execution."""

    task_id: str
    status: TaskStatus
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    error: Optional[str] = None
    iterations: int = 0
    elapsed_time: float = 0.0


class Message(BaseModel):
    """OpenCode session message."""

    id: str
    role: str  # "user" or "assistant"
    parts: list[dict]
    timestamp: float
