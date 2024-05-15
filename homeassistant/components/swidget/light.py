"""Support for Swidget lights."""

from __future__ import annotations

import logging
import math
from typing import Any, cast

from swidget.swidgetdimmer import SwidgetDimmer
import voluptuous as vol  # type: ignore[import-untyped]

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import DOMAIN
from .coordinator import SwidgetDataUpdateCoordinator
from .entity import CoordinatedSwidgetEntity

_LOGGER = logging.getLogger(__name__)

BRIGHTNESS = "brightness"
BRIGHTNESS_SCALE = (0, 100)
VAL = vol.Range(min=0, max=100)
SWIDGET_SET_BRIGHTNESS_SCHEMA = cv.make_entity_service_schema({BRIGHTNESS: VAL})


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light."""
    coordinator: SwidgetDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    if coordinator.device.is_dimmer:
        async_add_entities(
            [SwidgetSmartDimmer(cast(SwidgetDimmer, coordinator.device), coordinator)]
        )


class SwidgetSmartDimmer(CoordinatedSwidgetEntity, LightEntity):
    """Representation of a Swidget Dimmer."""

    device: SwidgetDimmer
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            brightness = math.ceil(
                brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])
            )
        await self._async_turn_on_with_brightness(brightness)

    async def _async_turn_on_with_brightness(self, brightness: int | None) -> None:
        # Fallback to adjusting brightness or turning the bulb on
        if brightness is not None:
            await self.device.set_brightness(brightness)
            # await self.coordinator._async_update_data()
            return
        await self.device.turn_on()
        # await self.coordinator._async_update_data()

    # @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.device.turn_off()
        # await self.coordinator._async_update_data()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return value_to_brightness(BRIGHTNESS_SCALE, self.device.brightness)

    async def set_default_brightness(self, **kwargs: Any) -> None:
        """Set the default brightness of the light."""
        if BRIGHTNESS in kwargs:
            await self.device.set_default_brightness(kwargs[BRIGHTNESS])

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return bool(self.device.is_on)
