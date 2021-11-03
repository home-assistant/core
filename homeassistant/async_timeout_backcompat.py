"""Provide backwards compat for async_timeout."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import async_timeout

from homeassistant.helpers.frame import (
    MissingIntegrationFrame,
    get_integration_frame,
    report_integration,
)

_LOGGER = logging.getLogger(__name__)


def timeout(
    delay: float | None, loop: asyncio.AbstractEventLoop | None = None
) -> async_timeout.Timeout:
    """Backwards compatible timeout context manager that warns with loop usage."""
    if loop is None:
        loop = asyncio.get_running_loop()
    else:
        _report(
            "called async_timeout.timeout with loop keyword argument. The loop keyword argument is deprecated and calls will fail after Home Assistant 2022.2"
        )
    if delay is not None:
        deadline: float | None = loop.time() + delay
    else:
        deadline = None
    return async_timeout.Timeout(deadline, loop)


def current_task(loop: asyncio.AbstractEventLoop) -> asyncio.Task[Any] | None:
    """Backwards compatible current_task."""
    _report(
        "called async_timeout.current_task. The current_task call is deprecated and calls will fail after Home Assistant 2022.2; use asyncio.current_task instead"
    )
    return asyncio.current_task()


def enable() -> None:
    """Enable backwards compat transitions."""
    async_timeout.timeout = timeout
    async_timeout.current_task = current_task  # type: ignore[attr-defined]


def _report(what: str) -> None:
    """Report incorrect usage.

    Async friendly.
    """
    integration_frame = None

    with contextlib.suppress(MissingIntegrationFrame):
        integration_frame = get_integration_frame()

    if not integration_frame:
        _LOGGER.warning(
            "Detected code that %s; Please report this issue", what, stack_info=True
        )
        return

    report_integration(what, integration_frame)
