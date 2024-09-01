"""asyncio loop utilities."""

from __future__ import annotations

from collections.abc import Callable
import functools
from functools import cache
import linecache
import logging
import threading
import traceback
from typing import Any

from homeassistant.core import async_get_hass_or_none
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


# Set of previously reported blocking calls
# (integration, filename, lineno)
_PREVIOUSLY_REPORTED: set[tuple[str | None, str, int | Any]] = set()


def raise_for_blocking_call(
    func: Callable[..., Any],
    check_allowed: Callable[[dict[str, Any]], bool] | None = None,
    strict: bool = True,
    strict_core: bool = True,
    **mapped_args: Any,
) -> None:
    """Warn if called inside the event loop. Raise if `strict` is True."""
    if check_allowed is not None and check_allowed(mapped_args):
        return

    found_frame = None
    offender_frame = get_current_frame(2)
    offender_filename = offender_frame.f_code.co_filename
    offender_lineno = offender_frame.f_lineno
    offender_line = _get_line_from_cache(offender_filename, offender_lineno)
    report_key: tuple[str | None, str, int | Any]

    try:
        integration_frame = get_integration_frame()
    except MissingIntegrationFrame:
        # Did not source from integration? Hard error.
        report_key = (None, offender_filename, offender_lineno)
        was_reported = report_key in _PREVIOUSLY_REPORTED
        _PREVIOUSLY_REPORTED.add(report_key)
        if not strict_core:
            if was_reported:
                _LOGGER.debug(
                    "Detected blocking call to %s with args %s in %s, "
                    "line %s: %s inside the event loop; "
                    "This is causing stability issues. "
                    "Please create a bug report at "
                    "https://github.com/home-assistant/core/issues?q=is%%3Aopen+is%%3Aissue\n"
                    "%s\n",
                    func.__name__,
                    mapped_args.get("args"),
                    offender_filename,
                    offender_lineno,
                    offender_line,
                    _dev_help_message(func.__name__),
                )
            else:
                _LOGGER.warning(
                    "Detected blocking call to %s with args %s in %s, "
                    "line %s: %s inside the event loop; "
                    "This is causing stability issues. "
                    "Please create a bug report at "
                    "https://github.com/home-assistant/core/issues?q=is%%3Aopen+is%%3Aissue\n"
                    "%s\n"
                    "Traceback (most recent call last):\n%s",
                    func.__name__,
                    mapped_args.get("args"),
                    offender_filename,
                    offender_lineno,
                    offender_line,
                    _dev_help_message(func.__name__),
                    "".join(traceback.format_stack(f=offender_frame)),
                )
            return

        if found_frame is None:
            raise RuntimeError(  # noqa: TRY200
                f"Caught blocking call to {func.__name__} with args {mapped_args.get("args")} "
                f"in {offender_filename}, line {offender_lineno}: {offender_line} "
                "inside the event loop; "
                "This is causing stability issues. "
                "Please create a bug report at "
                "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue\n"
                f"{_dev_help_message(func.__name__)}"
            )

    report_key = (integration_frame.integration, offender_filename, offender_lineno)
    was_reported = report_key in _PREVIOUSLY_REPORTED
    _PREVIOUSLY_REPORTED.add(report_key)

    report_issue = async_suggest_report_issue(
        async_get_hass_or_none(),
        integration_domain=integration_frame.integration,
        module=integration_frame.module,
    )

    if was_reported:
        _LOGGER.debug(
            "Detected blocking call to %s with args %s "
            "inside the event loop by %sintegration '%s' "
            "at %s, line %s: %s (offender: %s, line %s: %s), please %s\n"
            "%s\n",
            func.__name__,
            mapped_args.get("args"),
            "custom " if integration_frame.custom_integration else "",
            integration_frame.integration,
            integration_frame.relative_filename,
            integration_frame.line_number,
            integration_frame.line,
            offender_filename,
            offender_lineno,
            offender_line,
            report_issue,
            _dev_help_message(func.__name__),
        )
    else:
        _LOGGER.warning(
            "Detected blocking call to %s with args %s "
            "inside the event loop by %sintegration '%s' "
            "at %s, line %s: %s (offender: %s, line %s: %s), please %s\n"
            "%s\n"
            "Traceback (most recent call last):\n%s",
            func.__name__,
            mapped_args.get("args"),
            "custom " if integration_frame.custom_integration else "",
            integration_frame.integration,
            integration_frame.relative_filename,
            integration_frame.line_number,
            integration_frame.line,
            offender_filename,
            offender_lineno,
            offender_line,
            report_issue,
            _dev_help_message(func.__name__),
            "".join(traceback.format_stack(f=integration_frame.frame)),
        )

    if strict:
        raise RuntimeError(
            f"Caught blocking call to {func.__name__} with args "
            f"{mapped_args.get('args')} inside the event loop by "
            f"{'custom ' if integration_frame.custom_integration else ''}"
            f"integration '{integration_frame.integration}' at "
            f"{integration_frame.relative_filename}, line {integration_frame.line_number}:"
            f" {integration_frame.line}. (offender: {offender_filename}, line "
            f"{offender_lineno}: {offender_line}), please {report_issue}\n"
            f"{_dev_help_message(func.__name__)}"
        )


@cache
def _dev_help_message(what: str) -> str:
    """Generate help message to guide developers."""
    return (
        "For developers, please see "
        "https://developers.home-assistant.io/docs/asyncio_blocking_operations/"
        f"#{what.replace('.', '')}"
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
