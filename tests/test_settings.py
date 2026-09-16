"""Tests for application settings loading and initialisation."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from digest import cache, settings
from digest.cache import DataCache
from digest.constants import ROOT_DIR
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


def test_settings_read_the_repository_dotenv_file() -> None:
    """Settings take the repository .env file as a source.

    Without it the CLI only runs under Task, which loads the file itself.
    Runs in a subprocess because the isolation fixture detaches that source
    from this interpreter, so only a fresh one sees the declared setting.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from digest.settings import ApplicationSettings\n"
            "print(ApplicationSettings.model_config['env_file'])",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(ROOT_DIR / ".env")


def test_settings_load_values_from_the_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A variable present only in the dotenv file reaches the settings.

    Args:
        tmp_path: Pytest fixture supplying a temporary directory.
        monkeypatch: Pytest fixture for pointing settings at that directory.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=dotenv-key\n")
    monkeypatch.setitem(ApplicationSettings.model_config, "env_file", env_file)

    assert ApplicationSettings().openai_api_key == "dotenv-key"


def test_settings_ignore_unrelated_dotenv_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Variables the Taskfile reads do not fail validation.

    The same file carries the deployment variables read by the Taskfile, none
    of which name a settings field.

    Args:
        tmp_path: Pytest fixture supplying a temporary directory.
        monkeypatch: Pytest fixture for pointing settings at that directory.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=dotenv-key\n"
        "SITE_IDENTITY=~/.ssh/id_ed25519\n"
        "SITE_USER=digest\n"
        "SITE_HOST=example.test\n"
    )
    monkeypatch.setitem(ApplicationSettings.model_config, "env_file", env_file)

    assert ApplicationSettings().openai_api_key == "dotenv-key"


def test_isolated_settings_detaches_the_dotenv_file() -> None:
    """Tests never read the dotenv file sitting in the repository root.

    A developer's own file holds a live key, which would mask a test relying on
    credentials it never set.
    """
    assert ApplicationSettings.model_config["env_file"] is None
