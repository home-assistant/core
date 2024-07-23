"""Helpers for WLED."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from wled import WLEDConnectionError, WLEDError

from homeassistant.exceptions import HomeAssistantError

from .entity import WLEDEntity


def wled_exception_handler[_WLEDEntityT: WLEDEntity, **_P](
    func: Callable[Concatenate[_WLEDEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_WLEDEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate WLED calls to handle WLED exceptions.

    A decorator that wraps the passed in function, catches WLED errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(self: _WLEDEntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except WLEDConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError("Error communicating with WLED API") from error

        except WLEDError as error:
            raise HomeAssistantError("Invalid response from WLED API") from error

    return handler


def kelvinTo255(k: int, minK: int, maxK: int) -> int:
    """Map color temperature in K from minK-maxK to 0-255."""
    return int((k - minK) / (maxK - minK) * 255)


def kelvinTo255Reverse(v: int, minK: int, maxK: int) -> int:
    """Map color temperature from 0-255 to minK-maxK K."""
    return int(v / 255 * (maxK - minK) + minK)
