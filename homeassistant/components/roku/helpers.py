"""Helpers for Roku."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, TypeVar

from rokuecp import RokuConnectionError, RokuConnectionTimeoutError, RokuError
from typing_extensions import Concatenate, ParamSpec

from .entity import RokuEntity

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T", bound=RokuEntity)
_P = ParamSpec("_P")


def format_channel_name(channel_number: str, channel_name: str | None = None) -> str:
    """Format a Roku Channel name."""
    if channel_name is not None and channel_name != "":
        return f"{channel_name} ({channel_number})"

    return channel_number


def roku_exception_handler(ignore_timeout: bool = False) -> Callable[..., Callable]:
    """Decorate Roku calls to handle Roku exceptions."""

    def decorator(
        func: Callable[Concatenate[_T, _P], Awaitable[None]],  # type: ignore[misc]
    ) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:  # type: ignore[misc]
        @wraps(func)
        async def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
            try:
                await func(self, *args, **kwargs)
            except RokuConnectionTimeoutError as error:
                if not ignore_timeout and self.available:
                    _LOGGER.error("Error communicating with API: %s", error)
            except RokuConnectionError as error:
                if self.available:
                    _LOGGER.error("Error communicating with API: %s", error)
            except RokuError as error:
                if self.available:
                    _LOGGER.error("Invalid response from API: %s", error)

        return wrapper

    return decorator
