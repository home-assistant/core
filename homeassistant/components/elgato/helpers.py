"""Helpers for Elgato."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from elgato import ElgatoConnectionError, ElgatoError

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import ElgatoData
from .entity import ElgatoEntity

# Elgato lights that can do color reach less far at either end.
COLOR_TEMPERATURE_RANGE = (2900, 6993)  # 344 - 143 mireds
COLOR_TEMPERATURE_RANGE_COLOR = (3500, 6500)  # 285 - 153 mireds

COLOR_CAPABLE_PRODUCTS = ("Elgato Light Strip", "Elgato Light Strip Pro")


def supports_color(data: ElgatoData) -> bool:
    """Return if an Elgato Light does more than white."""
    return bool(
        data.info.product_name in COLOR_CAPABLE_PRODUCTS
        or data.settings.power_on_hue
        or data.state.hue is not None
    )


def color_temperature_range(data: ElgatoData) -> tuple[int, int]:
    """Return the color temperature range in Kelvin a device supports."""
    if supports_color(data):
        return COLOR_TEMPERATURE_RANGE_COLOR
    return COLOR_TEMPERATURE_RANGE


def elgato_exception_handler[_ElgatoEntityT: ElgatoEntity, **_P](
    func: Callable[Concatenate[_ElgatoEntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_ElgatoEntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Elgato calls to handle Elgato exceptions.

    A decorator that wraps the passed in function, catches Elgato errors,
    and raises a translated ``HomeAssistantError``.
    """

    async def handler(
        self: _ElgatoEntityT, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
        except ElgatoConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error
        except ElgatoError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
            ) from error

    return handler
