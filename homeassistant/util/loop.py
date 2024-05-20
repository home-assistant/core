"""asyncio loop utilities."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
import functools
import linecache
import logging
import threading
from typing import Any

from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.frame import (
    MissingIntegrationFrame,
    get_current_frame,
    get_integration_frame,
)
from homeassistant.loader import async_suggest_report_issue

_LOGGER = logging.getLogger(__name__)


def _get_line_from_cache(filename: str, lineno: int) -> str:
    """Get line from cache or read from file."""
    return (linecache.getline(filename, lineno) or "?").strip()


def raise_for_blocking_call(
    func: Callable[..., Any],
    check_allowed: Callable[[dict[str, Any]], bool] | None = None,
    strict: bool = True,
    strict_core: bool = True,
    advise_msg: str | None = None,
    **mapped_args: Any,
) -> None:
    """Warn if called inside the event loop. Raise if `strict` is True.

    The default advisory message is 'Use `await hass.async_add_executor_job()'
    Set `advise_msg` to an alternate message if the solution differs.
    """
    if check_allowed is not None and check_allowed(mapped_args):
        return

    found_frame = None
    offender_frame = get_current_frame(2)
    offender_filename = offender_frame.f_code.co_filename
    offender_lineno = offender_frame.f_lineno
    offender_line = _get_line_from_cache(offender_filename, offender_lineno)

    try:
        integration_frame = get_integration_frame()
    except MissingIntegrationFrame:
        # Did not source from integration? Hard error.
        if not strict_core:
            _LOGGER.warning(
                "Detected blocking call to %s with args %s in %s, "
                "line %s: %s inside the event loop",
                func.__name__,
                mapped_args.get("args"),
                offender_filename,
                offender_lineno,
                offender_line,
            )
            return

        if found_frame is None:
            raise RuntimeError(  # noqa: TRY200
                f"Detected blocking call to {func.__name__} inside the event loop "
                f"in {offender_filename}, line {offender_lineno}: {offender_line}. "
                f"{advise_msg or 'Use `await hass.async_add_executor_job()`'}; "
                "This is causing stability issues. Please create a bug report at "
                f"https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
            )

    hass: HomeAssistant | None = None
    with suppress(HomeAssistantError):
        hass = async_get_hass()
    report_issue = async_suggest_report_issue(
        hass,
        integration_domain=integration_frame.integration,
        module=integration_frame.module,
    )

    _LOGGER.warning(
        (
            "Detected blocking call to %s inside the event loop by %sintegration '%s' "
            "at %s, line %s: %s (offender: %s, line %s: %s), please %s"
        ),
        func.__name__,
        "custom " if integration_frame.custom_integration else "",
        integration_frame.integration,
        integration_frame.relative_filename,
        integration_frame.line_number,
        integration_frame.line,
        offender_filename,
        offender_lineno,
        offender_line,
        report_issue,
    )

    if strict:
        raise RuntimeError(
            "Blocking calls must be done in the executor or a separate thread;"
            f" {advise_msg or 'Use `await hass.async_add_executor_job()`'}; at"
            f" {integration_frame.relative_filename}, line {integration_frame.line_number}:"
            f" {integration_frame.line} "
            f"(offender: {offender_filename}, line {offender_lineno}: {offender_line})"
        )


def protect_loop[**_P, _R](
    func: Callable[_P, _R],
    loop_thread_id: int,
    strict: bool = True,
    strict_core: bool = True,
    check_allowed: Callable[[dict[str, Any]], bool] | None = None,
) -> Callable[_P, _R]:
    """Protect function from running in event loop."""

    @functools.wraps(func)
    def protected_loop_func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        if threading.get_ident() == loop_thread_id:
            raise_for_blocking_call(
                func,
                strict=strict,
                strict_core=strict_core,
                check_allowed=check_allowed,
                args=args,
                kwargs=kwargs,
            )
        return func(*args, **kwargs)

    return protected_loop_func
