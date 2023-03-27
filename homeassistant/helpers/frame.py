"""Provide frame helper for finding the current frame context."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
import logging
from traceback import FrameSummary, extract_stack
from typing import Any, TypeVar, cast

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

# Keep track of integrations already reported to prevent flooding
_REPORTED_INTEGRATIONS: set[str] = set()

_CallableT = TypeVar("_CallableT", bound=Callable)


def get_integration_frame(
    exclude_integrations: set | None = None,
) -> tuple[FrameSummary, str, str]:
    """Return the frame, integration and integration path of the current stack frame."""
    found_frame = None
    if not exclude_integrations:
        exclude_integrations = set()

    for frame in reversed(extract_stack()):
        for path in ("custom_components/", "homeassistant/components/"):
            try:
                index = frame.filename.index(path)
                start = index + len(path)
                end = frame.filename.index("/", start)
                integration = frame.filename[start:end]
                if integration not in exclude_integrations:
                    found_frame = frame

                break
            except ValueError:
                continue

        if found_frame is not None:
            break

    if found_frame is None:
        raise MissingIntegrationFrame

    return found_frame, integration, path


class MissingIntegrationFrame(HomeAssistantError):
    """Raised when no integration is found in the frame."""


def report(
    what: str,
    exclude_integrations: set | None = None,
    error_if_core: bool = True,
    level: int = logging.WARNING,
) -> None:
    """Report incorrect usage.

    Async friendly.
    """
    try:
        integration_frame = get_integration_frame(
            exclude_integrations=exclude_integrations
        )
    except MissingIntegrationFrame as err:
        msg = f"Detected code that {what}. Please report this issue."
        if error_if_core:
            raise RuntimeError(msg) from err
        _LOGGER.warning(msg, stack_info=True)
        return

    report_integration(what, integration_frame, level)


def report_integration(
    what: str,
    integration_frame: tuple[FrameSummary, str, str],
    level: int = logging.WARNING,
) -> None:
    """Report incorrect usage in an integration.

    Async friendly.
    """
    found_frame, integration, path = integration_frame

    # Keep track of integrations already reported to prevent flooding
    key = f"{found_frame.filename}:{found_frame.lineno}"
    if key in _REPORTED_INTEGRATIONS:
        return
    _REPORTED_INTEGRATIONS.add(key)

    index = found_frame.filename.index(path)
    if path == "custom_components/":
        extra = " to the custom integration author"
    else:
        extra = ""

    _LOGGER.log(
        level,
        (
            "Detected integration that %s. "
            "Please report issue%s for %s using this method at %s, line %s: %s"
        ),
        what,
        extra,
        integration,
        found_frame.filename[index:],
        found_frame.lineno,
        (found_frame.line or "?").strip(),
    )


def warn_use(func: _CallableT, what: str) -> _CallableT:
    """Mock a function to warn when it was about to be used."""
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def report_use(*args: Any, **kwargs: Any) -> None:
            report(what)

    else:

        @functools.wraps(func)
        def report_use(*args: Any, **kwargs: Any) -> None:
            report(what)

    return cast(_CallableT, report_use)
