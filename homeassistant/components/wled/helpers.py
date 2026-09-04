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


def white_channels_to_cct(cold: int, warm: int) -> tuple[int, int]:
    """Convert cold/warm white channel values to (CCT, brightness).

    CCT is represented on a 0..255 scale:
        0 = fully warm
        127 = neutral midpoint
        255 = fully cold

    Brightness is the maximum of the two channel values.
    """
    brightness = max(cold, warm)
    if brightness == 0:
        return 127, 0
    if warm == brightness:
        cct = round(cold * 127 / brightness)
    else:
        cct = 255 - round(warm * 128 / brightness)
    return cct, brightness


def cct_to_white_channels(cct: int, brightness: int) -> tuple[int, int]:
    """Convert a 0..255 CCT value and brightness to cold/warm channels.

    CCT:
        0 = fully warm
        127 = neutral midpoint
        255 = fully cold

    Brightness: 0..255
    """
    if cct <= 127:
        # At low CCT values (warm end), keep warm white at full
        # brightness and scale in cold white as CCT increases.
        cold = round(cct * brightness / 127)
        warm = brightness
    else:
        # At high CCT values (cold end), keep cold white at full
        # brightness and scale out warm white as CCT increases.
        cold = brightness
        warm = round((255 - cct) * brightness / 128)
    return cold, warm
