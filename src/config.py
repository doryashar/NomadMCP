"""Configuration management for NomadMCP."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Configuration for OpenCode server spawning."""

    binary_path: str = Field(default="opencode", description="Path to opencode binary")
    startup_timeout: float = Field(default=10.0, description="Server startup timeout in seconds")
    default_agent: Optional[str] = Field(default=None, description="Default agent name")


class PRConfig(BaseModel):
    """Configuration for PR management."""

    poll_interval: float = Field(default=30.0, description="PR polling interval in seconds")
    feedback_wait_multiplier: float = Field(
        default=2.0, description="Multiplier for wait time after sending feedback"
    )


class TaskConfig(BaseModel):
    """Configuration for task execution."""

    default_timeout_minutes: int = Field(default=60, description="Default task timeout in minutes")
    branch_prefix: str = Field(default="task", description="Prefix for auto-generated branch names")
    max_parallel_tasks: int = Field(default=5, description="Maximum number of parallel tasks")
    use_worktrees: bool = Field(
        default=True,
        description="Use git worktrees for parallel tasks on same directory"
    )
    persistence_file: Optional[str] = Field(
        default=None,
        description="Path to task persistence file (for recovery after restart)"
    )


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Path to log file")


class NomadMCPConfig(BaseModel):
    """Main configuration for NomadMCP."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    pr: PRConfig = Field(default_factory=PRConfig)
    task: TaskConfig = Field(default_factory=TaskConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_env(cls) -> "NomadMCPConfig":
        """Load configuration from environment variables.

        Environment variables:
        - NOMAD_MCP_OPENCODE_BINARY: Path to opencode binary
        - NOMAD_MCP_SERVER_TIMEOUT: Server startup timeout
        - NOMAD_MCP_PR_POLL_INTERVAL: PR polling interval
        - NOMAD_MCP_DEFAULT_TIMEOUT: Default task timeout in minutes
        - NOMAD_MCP_LOG_LEVEL: Logging level
        - NOMAD_MCP_LOG_FILE: Log file path

        Returns:
            Configuration instance
        """
        return cls(
            server=ServerConfig(
                binary_path=os.getenv("NOMAD_MCP_OPENCODE_BINARY", "opencode"),
                startup_timeout=float(os.getenv("NOMAD_MCP_SERVER_TIMEOUT", "10.0")),
            ),
            pr=PRConfig(
                poll_interval=float(os.getenv("NOMAD_MCP_PR_POLL_INTERVAL", "30.0")),
            ),
            task=TaskConfig(
                default_timeout_minutes=int(os.getenv("NOMAD_MCP_DEFAULT_TIMEOUT", "60")),
                branch_prefix=os.getenv("NOMAD_MCP_BRANCH_PREFIX", "task"),
                max_parallel_tasks=int(os.getenv("NOMAD_MCP_MAX_PARALLEL_TASKS", "5")),
                use_worktrees=os.getenv("NOMAD_MCP_USE_WORKTREES", "true").lower() == "true",
                persistence_file=os.getenv("NOMAD_MCP_PERSISTENCE_FILE"),
            ),
            logging=LoggingConfig(
                level=os.getenv("NOMAD_MCP_LOG_LEVEL", "INFO"),
                log_file=os.getenv("NOMAD_MCP_LOG_FILE"),
            ),
        )

    @classmethod
    def from_file(cls, path: str) -> "NomadMCPConfig":
        """Load configuration from JSON file.

        Args:
            path: Path to configuration file

        Returns:
            Configuration instance
        """
        import json

        with open(path, "r") as f:
            data = json.load(f)

        return cls(**data)

    def to_file(self, path: str) -> None:
        """Save configuration to JSON file.

        Args:
            path: Path to save configuration
        """
        import json

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)


# Global config instance
_config: Optional[NomadMCPConfig] = None


def get_config() -> NomadMCPConfig:
    """Get the global configuration instance.

    Returns:
        Configuration instance
    """
    global _config
    if _config is None:
        _config = NomadMCPConfig.from_env()
    return _config


def set_config(config: NomadMCPConfig) -> None:
    """Set the global configuration instance.

    Args:
        config: Configuration instance
    """
    global _config
    _config = config
