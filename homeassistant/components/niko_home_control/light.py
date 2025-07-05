"""Light platform Niko Home Control."""

from __future__ import annotations

from typing import Any

from nhc.light import NHCLight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    brightness_supported,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NHCController, NikoHomeControlConfigEntry
from .entity import NikoHomeControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Niko Home Control light entry."""
    controller = entry.runtime_data

    async_add_entities(
        NikoHomeControlLight(light, controller, entry.entry_id)
        for light in controller.lights
    )


class NikoHomeControlLight(NikoHomeControlEntity, LightEntity):
    """Representation of a Niko Light."""

    _attr_name = None
    _action: NHCLight

    def __init__(
        self, action: NHCLight, controller: NHCController, unique_id: str
    ) -> None:
        """Set up the Niko Home Control light platform."""
        super().__init__(action, controller, unique_id)
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if action.is_dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_brightness = action.state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        await self._action.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._action.turn_off()

    def update_state(self) -> None:
        """Handle updates from the controller."""
        state = self._action.state
        self._attr_is_on = state > 0
        if brightness_supported(self.supported_color_modes):
            self._attr_brightness = state
