"""Helper to help coordinating calls."""
from __future__ import annotations

import asyncio
import functools
from typing import Callable, TypeVar, cast

from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass

T = TypeVar("T")

FUNC = Callable[[HomeAssistant], T]


def singleton(data_key: str) -> Callable[[FUNC], FUNC]:
    """Decorate a function that should be called once per instance.

    Result will be cached and simultaneous calls will be handled.
    """

    def wrapper(func: FUNC) -> FUNC:
        """Wrap a function with caching logic."""
        if not asyncio.iscoroutinefunction(func):

            @bind_hass
            @functools.wraps(func)
            def wrapped(hass: HomeAssistant) -> T:
                obj: T | None = hass.data.get(data_key)
                if obj is None:
                    obj = hass.data[data_key] = func(hass)
                return obj

            return wrapped

        @bind_hass
        @functools.wraps(func)
        async def async_wrapped(hass: HomeAssistant) -> T:
            obj_or_evt = hass.data.get(data_key)

            if not obj_or_evt:
                evt = hass.data[data_key] = asyncio.Event()

                result = await func(hass)

                hass.data[data_key] = result
                evt.set()
                return cast(T, result)

            if isinstance(obj_or_evt, asyncio.Event):
                evt = obj_or_evt
                await evt.wait()
                return cast(T, hass.data.get(data_key))

            return cast(T, obj_or_evt)

        return async_wrapped

    return wrapper
