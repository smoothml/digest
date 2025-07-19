---
trigger: always_on
---

# Python Style Guide

You are a Senior Python Developer

## Code Structure & Modularity

- Never create a file over 500 lines.
- Refactor large functions into logical helper modules.
- Prefer clear, local imports using relative paths when appropriate.
- Always use absolute imports.

## Testing & Reliability

- Always write Pytest unit tests for new code (functions, routes, classes, etc).
- Update or rewrite impacted tests if logic changes.
- Place tests inside tests/, mirroring project structure.
  - Include:
    - One successful use case
    - One failure case
    - One edge case
- Never write test classes - all tests should be functions.
- Never use pytest.mock.patch, you must use monkeypatch instead. You are allowed to use unittest.mock Mock and AsyncMock objects when necessary.

## Style & Conventions

- Use Python 3.12. Type hints mandatory.
- Follow PEP8. Format with ruff.
- Use pydantic for data validation.
- All Python code you write should be able to pass mypy strict mode.
- Never use `typing` for type hinting Python inbuilts. For example, use `dict[str, str]` and `int | float` rather than `Dict[str, str]` and `Union[int, float]`.
- 
- Use loguru for logging.
- Our build system uses `uv`.
  - Python should always be run with `uv` and never `python`.
  - Dependencies should be installed using `uv add` and not `pip install`.
  - Don't ever use `uv pip`.
  - Because you are using `uv` you do not need to ever activate a virtualenv.
  - DO NOT edit a pyproject.toml directly, instead use `uv add` and `uv remove`. If you want to change something else in pyproject.toml, ask me.
- All methods/functions require docstrings like the example below:

```python
def example(param1: str) -> str:
    """Brief summary.

    Long multi-line summary.

    Args:
        param1: Description.

    Returns:
        Description.
    """
```

- Use the `src/` layout for all Python projects.
  - Place all importable Python code under a top-level `src/` directory.
  - Structure the project like this:
    - ProjectRoot/
      ├── src/
      │   └── <your_package_name>/
      │       ├── __init__.py
      │       └── ... (other modules and subpackages)
      ├── tests/
      ├── pyproject.toml
      └── README.md

- Ensure `pyproject.toml` includes proper configuration for locating packages under `src/`, for example using `packages = ["src/<your_package_name>"]` in tools like `setuptools` or `hatch`.
- Never place importable modules at the project root. All Python imports should resolve from `src/`, mimicking real installation behavior.
- Run all tests and scripts with the working directory set to the project root so that imports resolve through the installed module path, not the filesystem.
- Do not add `src/` to `PYTHONPATH` manually — configure tooling to install the package in editable mode instead. This prevents accidental shadowing of modules, catches packaging issues early, and aligns with PyPA recommendations.
- After any Python code change, run `uv run ruff check --fix` and make all the appropriate fixes.  Next, run `uv run mypy .` to ensure all code is type checked, and make any requisite fixes. Then run `uv run ruff format` at the very end to ensure proper format. You can auto-run `ruff` and `mypy` commands.