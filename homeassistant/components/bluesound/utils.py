"""Utility functions for the Bluesound component."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

from homeassistant.helpers.device_registry import format_mac


def format_unique_id(mac: str, port: int) -> str:
    """Generate a unique ID based on the MAC address and port number."""
    return f"{format_mac(mac)}-{port}"


def throttled(
    delta: timedelta,
) -> Callable[[Callable[[Any], Awaitable[None]]], Callable[[Any], Awaitable[None]]]:
    """Throttle calls to the decorated function. Calls which are within the delta time will be ignored."""

    def decorator(
        func: Callable[[Any], Awaitable[None]],
    ) -> Callable[[Any], Awaitable[None]]:
        last_call = None

        @wraps(func)
        async def wrapper(value: Any) -> None:
            nonlocal last_call
            now = datetime.now()
            # mypy thinks last_call is always None, but there are tests that prove otherwise
            if last_call is None or now - last_call > delta:  # type: ignore[unreachable]
                last_call = now
                await func(value)

        return wrapper

    return decorator
