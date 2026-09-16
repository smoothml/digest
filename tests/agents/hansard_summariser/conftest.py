"""Fixtures for the Hansard summariser agent tests."""

import pytest


@pytest.fixture(autouse=True)
def openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply the dummy key the agent factories need to build a provider.

    Args:
        monkeypatch: The built-in monkeypatch fixture.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
