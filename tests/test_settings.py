"""Tests for lazy application settings initialisation."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

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


def test_settings_reads_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Settings load variables from the configured env_file.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=dotenv-key\nOPENAI_BASE_URL=https://dotenv.test/v1\n"
    )

    monkeypatch.setitem(ApplicationSettings.model_config, "env_file", env_file)

    app_settings = ApplicationSettings()
    assert app_settings.openai_api_key == "dotenv-key"
    assert app_settings.openai_base_url == "https://dotenv.test/v1"


def test_settings_ignores_extra_attributes_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Extra variables in .env (e.g. Taskfile variables) are ignored without error.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=dotenv-key\n"
        "SITE_IDENTITY=test-site\n"
        "SITE_USER=deployer\n"
        "SITE_HOST=example.com\n"
    )

    monkeypatch.setitem(ApplicationSettings.model_config, "env_file", env_file)

    app_settings = ApplicationSettings()
    assert app_settings.openai_api_key == "dotenv-key"


def test_isolated_settings_neutralises_dotenv() -> None:
    """The root conftest neutralises env_file so ambient files do not satisfy settings."""
    assert ApplicationSettings.model_config.get("env_file") is None
    with pytest.raises(ValidationError) as exc_info:
        ApplicationSettings()
    assert "openai_api_key" in str(exc_info.value)
