"""Support for Big Ass Fans SenseME light."""
from __future__ import annotations

from typing import Any

from aiosenseme import SensemeDevice

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .const import DOMAIN
from .entity import SensemeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME lights."""
    device = hass.data[DOMAIN][entry.entry_id]
    if device.has_light:
        async_add_entities([HASensemeLight(device)])


class HASensemeLight(SensemeEntity, LightEntity):
    """Representation of a Big Ass Fans SenseME light."""

    def __init__(self, device: SensemeDevice) -> None:
        """Initialize the entity."""
        self._device = device
        if device.is_light:
            name = device.name  # The device itself is a light
        else:
            name = f"{device.name} Light"  # A fan light
        super().__init__(device, name)
        if device.is_light:
            self._attr_supported_color_modes = {COLOR_MODE_COLOR_TEMP}
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
        else:
            self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}
            self._attr_color_mode = COLOR_MODE_BRIGHTNESS
        self._attr_unique_id = f"{self._device.uuid}-LIGHT"  # for legacy compat
        self._attr_min_mireds = color_temperature_kelvin_to_mired(
            self._device.light_color_temp_max
        )
        self._attr_max_mireds = color_temperature_kelvin_to_mired(
            self._device.light_color_temp_min
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self._device.light_on
        self._attr_brightness = int(min(255, self._device.light_brightness * 16))
        self._attr_color_temp = color_temperature_kelvin_to_mired(
            self._device.light_color_temp
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if (color_temp := kwargs.get(ATTR_COLOR_TEMP)) is not None:
            self._device.light_color_temp = color_temperature_mired_to_kelvin(
                color_temp
            )
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            # set the brightness, which will also turn on/off light
            if brightness == 255:
                brightness = 256  # this will end up as 16 which is max
            self._device.light_brightness = int(brightness / 16)
        else:
            self._device.light_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._device.light_on = False
