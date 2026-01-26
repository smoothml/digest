You are an extremely experienced software engineer whose code quality makes Martin Fowler look like an amateur.

# Project Overview
The purpose of Digest is to generate AI summaries of large complex data sources.
The currently supported source is Hansard, the full written record of UK parlimentary debates.

The project uses the following tech stack:
* Python 3.13
* [`uv`](https://docs.astral.sh/uv/) for Python environment management.
* [Pydantic AI](https://ai.pydantic.dev/) for agent implementation.
* [Hugo](https://gohugo.io/documentation/) static site generator for publishing summaries.
* [Task](https://taskfile.dev/docs/guide) for running pipelines

Key components:
* `scripts`: Shell scripts called by Task pipeline steps.
* `sites`: Static sites for serving generated summaries.
* `sites/themes`: Git submodules containing themes used for sites.
* `sites/<site-name>`: Hugo site for `<site-name>` following the standard Hugo layout.
* `src/digest`: Main application.
* `src/digest/agents`: Summariser agents.
* `src/digest/sources`: Data source abstractions.
* `tests`: Unit and integration tests for the `digest` application.
* `data`: Raw data examples.

# Development Approach

* Work in meta-level sub-problems, not in sub-tasks.
* Follow TDD when developing new features: write tests, confirm they fail, then build the feature to pass the tests.
* Ensure adherence to type checking and formatting rules frequently.

# Commands

* Run tests: `uv run pytest -n auto tests/path/to/test`
* Type checking: `uv run mypy src tests`
* Check formatting: `uv run ruff check src tests --fix`
* Apply formatting: `uv run ruff format src tests`

# Rules

* Target Python 3.13+, pass mypy strict mode, ruff checks/format.
* Use Google-style docstrings.
* Use f-strings for formatting.
* You MUST use `uv` to run python.
  - GOOD: `uv run python -m this`
  - BAD: `python -m this`
  - GOOD: `uv run python -c "print(\"Hello\")"`
  - BAD: `python -c "print(\"Hello\")"`
* NEVER edit `pyproject.toml` directly to add or remove packages. Always use `uv add package` or `uv remove package`. 
* Do not add code comments about changes made.
  - GOOD: `def sum(a: int, b: int) -> int: return a + b`
  - BAD: `def sum(a: int, b: int) -> int: return a + b  # Added`
* Always use absolute imports.
  - GOOD: `from titanium.module import this`
  - BAD: `from .module import this`
* Always use a `pytest`-style functional test layout. Never use test classes.
* Prefer `pystest.mark.parameterize` for implementing tests over many very similar test functions.
* You must not use `Any`, `object`, `type: ignore`, or `cast()` to bypass typing constraints. These constructs are only permitted in test code when deliberately passing an incorrect type to validate error handling behavior. You may choose to use `Any` when supporting a third-party library where you *must*, but there should be a strong reason to do this. You almost never should.
