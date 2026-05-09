# Development Workflow

## Task Completion Checklist
Before finishing a task, ensure the following steps are taken:

1.  **Functionality**: Verify the changes solve the original problem or implement the requested feature.
2.  **Tests**: Run existing tests and add new ones if necessary.
    - Command: `uv run pytest tests`
3.  **Linting**: Check for code style violations.
    - Command: `uv run ruff check .`
4.  **Formatting**: Apply consistent formatting.
    - Command: `uv run ruff format .`
5.  **Manual Verification**: If possible, run the server and check the UI or API behavior.
    - Command: `uv run uvicorn main:app --reload`
