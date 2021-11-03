"""Provide backwards compat transitions."""

import asyncio
import contextlib
import logging
from typing import Optional

import async_timeout

from homeassistant.helpers.frame import (
    MissingIntegrationFrame,
    get_integration_frame,
    report_integration,
)

_LOGGER = logging.getLogger(__name__)


def timeout(
    delay: Optional[float], loop: Optional[asyncio.AbstractEventLoop] = None
) -> "async_timeout.Timeout":
    """Backwards compatible timeout context manager that warns with loop usage."""
    if loop is None:
        loop = asyncio.get_running_loop()
    else:
        _report(
            "called async_timeout.timeout with loop keyword argument. The loop keyword argument is deprecated and calls will fail after Home Assistant 2022.2"
        )
    if delay is not None:
        deadline = loop.time() + delay  # type: Optional[float]
    else:
        deadline = None
    return async_timeout.Timeout(deadline, loop)


def enable() -> None:
    """Enable backwards compat transitions."""
    async_timeout.timeout = timeout


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
