"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from loguru import logger


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
