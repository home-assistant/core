"""Helpers for Roku."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar

from rokuecp import RokuConnectionError, RokuConnectionTimeoutError, RokuError

from homeassistant.exceptions import HomeAssistantError

from .entity import RokuEntity

_RokuEntityT = TypeVar("_RokuEntityT", bound=RokuEntity)
_P = ParamSpec("_P")

_FuncType = Callable[Concatenate[_RokuEntityT, _P], Awaitable[Any]]
_ReturnFuncType = Callable[Concatenate[_RokuEntityT, _P], Coroutine[Any, Any, None]]


def format_channel_name(channel_number: str, channel_name: str | None = None) -> str:
    """Format a Roku Channel name."""
    if channel_name is not None and channel_name != "":
        return f"{channel_name} ({channel_number})"

    return channel_number


def roku_exception_handler(
    ignore_timeout: bool = False,
) -> Callable[[_FuncType[_RokuEntityT, _P]], _ReturnFuncType[_RokuEntityT, _P]]:
    """Decorate Roku calls to handle Roku exceptions."""

    def decorator(
        func: _FuncType[_RokuEntityT, _P]
    ) -> _ReturnFuncType[_RokuEntityT, _P]:
        @wraps(func)
        async def wrapper(
            self: _RokuEntityT, *args: _P.args, **kwargs: _P.kwargs
        ) -> None:
            try:
                await func(self, *args, **kwargs)
            except RokuConnectionTimeoutError as error:
                if not ignore_timeout:
                    raise HomeAssistantError(
                        "Timeout communicating with Roku API"
                    ) from error
            except RokuConnectionError as error:
                raise HomeAssistantError("Error communicating with Roku API") from error
            except RokuError as error:
                raise HomeAssistantError("Invalid response from Roku API") from error

        return wrapper

    return decorator
