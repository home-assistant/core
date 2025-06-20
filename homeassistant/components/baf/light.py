"""Support for Big Ass Fans lights."""

from __future__ import annotations

from typing import Any

from aiobafi6 import Device, OffOnAuto

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BAFConfigEntry
from .entity import BAFEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BAFConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BAF lights."""
    device = entry.runtime_data
    if device.has_light:
        klass = BAFFanLight if device.has_fan else BAFStandaloneLight
        async_add_entities([klass(device)])


class BAFLight(BAFEntity, LightEntity):
    """Representation of a Big Ass Fans light."""

    _attr_name = None

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self._device.light_mode == OffOnAuto.ON
        if self._device.light_brightness_level is not None:
            self._attr_brightness = round(
                self._device.light_brightness_level / 16 * 255
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._device.light_brightness_level = max(int(brightness / 255 * 16), 1)
        else:
            self._device.light_mode = OffOnAuto.ON

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._device.light_mode = OffOnAuto.OFF


class BAFFanLight(BAFLight):
    """Representation of a Big Ass Fans light on a fan."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS


class BAFStandaloneLight(BAFLight):
    """Representation of a Big Ass Fans light."""

    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP

    def __init__(self, device: Device) -> None:
        """Init a standalone light."""
        super().__init__(device)
        self._attr_max_color_temp_kelvin = device.light_warmest_color_temperature
        self._attr_min_color_temp_kelvin = device.light_coolest_color_temperature

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        super()._async_update_attrs()
        self._attr_color_temp_kelvin = self._device.light_color_temperature

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if (color_temp := kwargs.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
            self._device.light_color_temperature = color_temp
        await super().async_turn_on(**kwargs)
