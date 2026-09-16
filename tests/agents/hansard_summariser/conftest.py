"""Fixtures for the Hansard summariser agent tests."""

import pytest


@pytest.fixture(autouse=True)
def openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply the dummy key the agent factories need to build a provider.

    These tests construct real OpenAI providers, so they are the only ones
    needing a key. The root conftest strips the environment and clears the
    settings caches first, so this key reaches only this package.

    Args:
        monkeypatch: The built-in monkeypatch fixture.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
