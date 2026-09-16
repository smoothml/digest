"""Tests for lazy application settings initialisation."""

import os
import subprocess
import sys

import pytest

from digest import cache, settings
from digest.cache import DataCache
from digest.settings import ApplicationSettings, get_openai_provider

_UNSET_VARIABLES = frozenset({"OPENAI_API_KEY", "OPENAI_BASE_URL", "DATA_CACHE_URL"})


def test_provider_is_built_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider takes its credentials and base URL from settings.

    The surrounding fixtures strip both variables from the environment, so the
    OpenAI client cannot read them itself. Anything reaching the provider must
    have travelled through the settings accessor.

    Args:
        monkeypatch: Pytest fixture for replacing the settings accessor.
    """
    application_settings = ApplicationSettings(
        openai_api_key="test-key", openai_base_url="https://example.test/v1"
    )
    monkeypatch.setattr(
        settings, "get_application_settings", lambda: application_settings
    )

    provider = get_openai_provider()

    assert provider.client.api_key == "test-key"
    assert provider.base_url.rstrip("/") == "https://example.test/v1"


def test_data_cache_defaults_to_the_configured_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A data cache created without a URL falls back to the configured one.

    Args:
        monkeypatch: Pytest fixture for replacing the settings accessor.
    """
    application_settings = ApplicationSettings(
        openai_api_key="test-key", data_cache_url="memory://default-cache"
    )
    monkeypatch.setattr(cache, "get_application_settings", lambda: application_settings)

    DataCache().write("note.txt", "hello")

    assert DataCache("memory://default-cache").read("note.txt") == "hello"


@pytest.mark.parametrize(
    "module", ["digest.cache", "digest.agents.hansard_summariser.agent"]
)
def test_importing_module_does_not_require_credentials(module: str) -> None:
    """Modules importing settings can be imported without credentials.

    Runs in a subprocess because the module under test is already imported into
    this interpreter, so only a fresh one can observe its import side effects.

    Args:
        module: Dotted path of a module importing digest.settings directly.
    """
    environment = {
        key: value for key, value in os.environ.items() if key not in _UNSET_VARIABLES
    }

    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
