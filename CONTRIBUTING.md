# Contributing to NomadMCP

Thank you for your interest in contributing to NomadMCP! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- OpenCode CLI (`npm install -g @opencode/cli`)
- GitHub CLI (`brew install gh` or see [GitHub CLI docs](https://cli.github.com/))
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/doryashar/NomadMCP.git
cd NomadMCP
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements-dev.txt
```

4. Install pre-commit hooks (optional but recommended):
```bash
pre-commit install
```

## Project Structure

```
NomadMCP/
├── src/                      # Main source code
│   ├── server.py            # MCP server implementation
│   ├── types.py             # Data models
│   ├── config.py            # Configuration management
│   ├── logging_config.py    # Logging setup
│   ├── utils.py             # Utility functions
│   ├── git_manager.py       # Git operations
│   ├── process_manager.py   # OpenCode process management
│   ├── client_manager.py    # HTTP client for OpenCode API
│   ├── session_manager.py   # Session lifecycle
│   ├── pr_manager.py        # GitHub PR operations
│   └── task_orchestrator.py # Main orchestration logic
├── tests/                   # Test suite
│   ├── test_git_manager.py
│   └── test_utils.py
├── examples/                # Example configurations
└── docs/                    # Documentation (if any)
```

## Development Workflow

### Running Tests

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_git_manager.py
```

Run specific test:
```bash
pytest tests/test_git_manager.py::test_create_branch
```

### Code Quality

Format code:
```bash
black src/ tests/
```

Lint code:
```bash
ruff check src/ tests/
```

Type checking:
```bash
mypy src/
```

### Running the Server Locally

```bash
python3 -m src.server
```

Or with custom config:
```bash
export NOMAD_MCP_LOG_LEVEL=DEBUG
export NOMAD_MCP_LOG_FILE=nomad-mcp.log
python3 -m src.server
```

## Contributing Guidelines

### Code Style

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for all public functions and classes (Google style)
- Keep functions small and focused (single responsibility)
- Use meaningful variable names

### Example Function

```python
async def create_branch(
    self,
    directory: str,
    branch_name: str,
    from_branch: Optional[str] = None,
) -> None:
    """Create a new git branch.

    Args:
        directory: Path to repository
        branch_name: Name of new branch
        from_branch: Base branch (defaults to current branch)

    Raises:
        ValueError: If branch already exists
    """
    # Implementation...
```

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat(pr-manager): Add support for GitLab merge requests

- Implement GitLab API client
- Add MR polling logic
- Update configuration to support GitLab

Closes #123
```

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`pytest`)
6. Ensure code is formatted (`black .`) and linted (`ruff check .`)
7. Commit your changes
8. Push to your fork
9. Create a Pull Request

PR Requirements:
- All tests must pass
- Code coverage should not decrease
- Include tests for new features
- Update documentation if needed
- Follow the code style guidelines

### Adding New Features

1. **Propose the feature**: Open an issue to discuss the feature before implementing
2. **Design**: Document the design and get feedback
3. **Implement**: Write the code following style guidelines
4. **Test**: Add comprehensive tests
5. **Document**: Update README and add examples if needed
6. **Submit**: Create a PR with clear description

## Testing Guidelines

### Unit Tests

- Test individual functions and classes in isolation
- Use mocks for external dependencies
- Cover edge cases and error conditions
- Aim for >80% code coverage

### Integration Tests

Mark integration tests with `@pytest.mark.integration`:
```python
@pytest.mark.integration
async def test_full_task_workflow():
    # Test that requires external services
    pass
```

### Test Organization

```python
class TestGitManager:
    """Tests for GitManager."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary git repository."""
        # Setup
        yield repo
        # Teardown

    async def test_create_branch(self, temp_repo):
        """Test branch creation."""
        # Arrange
        manager = GitManager()

        # Act
        await manager.create_branch(temp_repo, "feature/test")

        # Assert
        assert await manager.branch_exists(temp_repo, "feature/test")
```

## Debugging

### Enable Debug Logging

```bash
export NOMAD_MCP_LOG_LEVEL=DEBUG
python3 -m src.server
```

### Common Issues

**OpenCode server not starting:**
- Check if `opencode` is in PATH
- Verify OpenCode installation: `opencode --version`
- Check logs for errors

**PR operations failing:**
- Verify GitHub CLI authentication: `gh auth status`
- Check if repository has a remote
- Verify `gh` has necessary permissions

**Tests failing:**
- Ensure test dependencies are installed: `pip install -r requirements-dev.txt`
- Check if git is configured: `git config user.name && git config user.email`

## Release Process

1. Update version in `src/__init__.py` and `pyproject.toml`
2. Update CHANGELOG.md
3. Create a git tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
4. Push tag: `git push origin v0.2.0`
5. Create GitHub release with release notes

## Getting Help

- Open an issue for bugs or feature requests
- Join discussions in GitHub Discussions
- Tag maintainers for urgent issues

## Code of Conduct

Be respectful and inclusive. We want this to be a welcoming community for all contributors.

## License

By contributing to NomadMCP, you agree that your contributions will be licensed under the MIT License.
