"""Support for Swidget lights."""

from __future__ import annotations

import logging
from typing import Any, cast

from swidget.swidgetdimmer import SwidgetDimmer

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import SwidgetConfigEntry
from .entity import CoordinatedSwidgetEntity

_LOGGER = logging.getLogger(__name__)
BRIGHTNESS = "brightness"
BRIGHTNESS_SCALE = (0, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwidgetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light."""
    coordinator = config_entry.runtime_data
    device = coordinator.device
    if device.is_dimmer:
        async_add_entities(
            [SwidgetSmartDimmer(cast(SwidgetDimmer, device), coordinator)]
        )


class SwidgetSmartDimmer(CoordinatedSwidgetEntity, LightEntity):
    """Representation of a Swidget Dimmer."""

    device: SwidgetDimmer
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            brightness = round(
                brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])
            )
        await self._async_turn_on_with_brightness(brightness)

    async def _async_turn_on_with_brightness(self, brightness: int | None) -> None:
        # Fallback to adjusting brightness or turning the bulb on
        if brightness is not None:
            await self.device.set_brightness(brightness)
            return
        await self.device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.device.turn_off()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return value_to_brightness(BRIGHTNESS_SCALE, self.device.brightness)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = bool(self.device.is_on)
        self._attr_brightness = value_to_brightness(
            BRIGHTNESS_SCALE, self.device.brightness
        )
        self.async_write_ha_state()

    async def set_default_brightness(self, **kwargs: Any) -> None:
        """Set the default brightness of the light."""
        if BRIGHTNESS in kwargs:
            await self.device.set_default_brightness(kwargs[BRIGHTNESS])
