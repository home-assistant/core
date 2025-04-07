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


def kelvin_to_255(k: int, min_k: int, max_k: int) -> int:
    """Map color temperature in K from minK-maxK to 0-255."""
    return int((k - min_k) / (max_k - min_k) * 255)


def kelvin_to_255_reverse(v: int, min_k: int, max_k: int) -> int:
    """Map color temperature from 0-255 to minK-maxK K."""
    return int(v / 255 * (max_k - min_k) + min_k)
