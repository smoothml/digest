"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from loguru import logger

from digest.settings import (
    ApplicationSettings,
    get_application_settings,
    get_openai_provider,
)


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Route Loguru records into pytest's log capture fixture.

    Loguru does not write through the standard library logging module, so
    the built-in fixture captures nothing by default. Adding its handler as
    a Loguru sink bridges the two for the duration of a test.

    Args:
        caplog: The built-in pytest log capture fixture.

    Yields:
        The log capture fixture, now also receiving Loguru records.
    """
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
        filter=lambda record: record["level"].no >= caplog.handler.level,
        enqueue=False,
    )
    yield caplog
    logger.remove(handler_id)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep ambient credentials and cached settings out of every test.

    Settings read the repository .env file, which on a developer machine holds
    a live key, so detach that source as well as the environment variables.

    Args:
        monkeypatch: The built-in monkeypatch fixture.

    Yields:
        None, once the environment is isolated.
    """
    for variable in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "DATA_CACHE_URL"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setitem(ApplicationSettings.model_config, "env_file", None)
    get_application_settings.cache_clear()
    get_openai_provider.cache_clear()
    yield
    get_application_settings.cache_clear()
    get_openai_provider.cache_clear()
