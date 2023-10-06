"""Provide frame helper for finding the current frame context."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import functools
import logging
import sys
from traceback import FrameSummary, extract_stack
from typing import Any, TypeVar, cast

from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_suggest_report_issue

_LOGGER = logging.getLogger(__name__)

# Keep track of integrations already reported to prevent flooding
_REPORTED_INTEGRATIONS: set[str] = set()

_CallableT = TypeVar("_CallableT", bound=Callable)


@dataclass(kw_only=True)
class IntegrationFrame:
    """Integration frame container."""

    custom_integration: bool
    frame: FrameSummary
    integration: str
    module: str | None
    relative_filename: str


def get_integration_frame(exclude_integrations: set | None = None) -> IntegrationFrame:
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

    found_module: str | None = None
    for module, module_obj in dict(sys.modules).items():
        if not hasattr(module_obj, "__file__"):
            continue
        if module_obj.__file__ == found_frame.filename:
            found_module = module
            break

    return IntegrationFrame(
        custom_integration=path == "custom_components/",
        frame=found_frame,
        integration=integration,
        module=found_module,
        relative_filename=found_frame.filename[index:],
    )


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

    _report_integration(what, integration_frame, level)


def _report_integration(
    what: str,
    integration_frame: IntegrationFrame,
    level: int = logging.WARNING,
) -> None:
    """Report incorrect usage in an integration.

    Async friendly.
    """
    found_frame = integration_frame.frame
    # Keep track of integrations already reported to prevent flooding
    key = f"{found_frame.filename}:{found_frame.lineno}"
    if key in _REPORTED_INTEGRATIONS:
        return
    _REPORTED_INTEGRATIONS.add(key)

    hass: HomeAssistant | None = None
    with suppress(HomeAssistantError):
        hass = async_get_hass()
    report_issue = async_suggest_report_issue(
        hass,
        integration_domain=integration_frame.integration,
        module=integration_frame.module,
    )

    _LOGGER.log(
        level,
        "Detected that %sintegration '%s' %s at %s, line %s: %s, please %s",
        "custom " if integration_frame.custom_integration else "",
        integration_frame.integration,
        what,
        integration_frame.relative_filename,
        found_frame.lineno,
        (found_frame.line or "?").strip(),
        report_issue,
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
