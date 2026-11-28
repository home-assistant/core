"""Helpers for WLED."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from wled import WLEDConnectionError, WLEDError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(error)},
            ) from error
        except WLEDError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_response_wled_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler


def kelvin_to_255(k: int, min_k: int, max_k: int) -> int:
    """Map color temperature in K from minK-maxK to 0-255."""
    return int((k - min_k) / (max_k - min_k) * 255)


def kelvin_to_255_reverse(v: int, min_k: int, max_k: int) -> int:
    """Map color temperature from 0-255 to minK-maxK K."""
    return int(v / 255 * (max_k - min_k) + min_k)


def kelvin_to_cct(kelvin: int, warm_kelvin: int, cold_kelvin: int) -> int:
    """Map a color temperature to WLED's 0 (warm) to 255 (cold) white mix.

    Two white LEDs mix linearly in mireds, not in kelvin.
    """
    warm, cold = 1_000_000 / warm_kelvin, 1_000_000 / cold_kelvin
    position = (1_000_000 / kelvin - warm) / (cold - warm)
    return round(min(max(position, 0), 1) * 255)


def cct_to_kelvin(cct: int, warm_kelvin: int, cold_kelvin: int) -> int:
    """Map WLED's 0 (warm) to 255 (cold) white mix to a color temperature."""
    warm, cold = 1_000_000 / warm_kelvin, 1_000_000 / cold_kelvin
    return round(1_000_000 / (warm + cct / 255 * (cold - warm)))
