"""Helper to help coordinating calls."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
from typing import TypeVar, cast

from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass

_T = TypeVar("_T")

FUNC = Callable[[HomeAssistant], _T]


def singleton(data_key: str) -> Callable[[FUNC], FUNC]:
    """Decorate a function that should be called once per instance.

    Result will be cached and simultaneous calls will be handled.
    """

    def wrapper(func: FUNC) -> FUNC:
        """Wrap a function with caching logic."""
        if not asyncio.iscoroutinefunction(func):

            @bind_hass
            @functools.wraps(func)
            def wrapped(hass: HomeAssistant) -> _T:
                if data_key not in hass.data:
                    hass.data[data_key] = func(hass)
                return cast(_T, hass.data[data_key])

            return wrapped

        @bind_hass
        @functools.wraps(func)
        async def async_wrapped(hass: HomeAssistant) -> _T:
            if data_key not in hass.data:
                evt = hass.data[data_key] = asyncio.Event()
                result = await func(hass)
                hass.data[data_key] = result
                evt.set()
                return cast(_T, result)

            obj_or_evt = hass.data[data_key]

            if isinstance(obj_or_evt, asyncio.Event):
                await obj_or_evt.wait()
                return cast(_T, hass.data[data_key])

            return cast(_T, obj_or_evt)

        return async_wrapped

    return wrapper
