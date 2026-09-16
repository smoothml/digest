"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from loguru import logger

from digest.settings import get_application_settings, get_openai_provider


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

    Removing the variables means the suite runs with no credentials unless a
    test asks for them, so reintroducing import-time settings construction
    breaks collection again. Clearing the caches stops one test's settings
    leaking into the next.

    Args:
        monkeypatch: The built-in monkeypatch fixture.

    Yields:
        None, once the environment is isolated.
    """
    for variable in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "DATA_CACHE_URL"):
        monkeypatch.delenv(variable, raising=False)
    get_application_settings.cache_clear()
    get_openai_provider.cache_clear()
    yield
    get_application_settings.cache_clear()
    get_openai_provider.cache_clear()
