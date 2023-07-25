"""Support for Big Ass Fans lights."""
from __future__ import annotations

from typing import Any

from aiobafi6 import Device, OffOnAuto

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .const import DOMAIN
from .entity import BAFEntity
from .models import BAFData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF lights."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    if data.device.has_light:
        klass = BAFFanLight if data.device.has_fan else BAFStandaloneLight
        async_add_entities([klass(data.device)])


class BAFLight(BAFEntity, LightEntity):
    """Representation of a Big Ass Fans light."""

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

    _attr_name = None

    def __init__(self, device: Device) -> None:
        """Init a fan light."""
        super().__init__(device)
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS


class BAFStandaloneLight(BAFLight):
    """Representation of a Big Ass Fans light."""

    def __init__(self, device: Device) -> None:
        """Init a standalone light."""
        super().__init__(device)
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        self._attr_color_mode = ColorMode.COLOR_TEMP
        self._attr_min_mireds = color_temperature_kelvin_to_mired(
            device.light_warmest_color_temperature
        )
        self._attr_max_mireds = color_temperature_kelvin_to_mired(
            device.light_coolest_color_temperature
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        super()._async_update_attrs()
        self._attr_color_temp = color_temperature_kelvin_to_mired(
            self._device.light_color_temperature
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if (color_temp := kwargs.get(ATTR_COLOR_TEMP)) is not None:
            self._device.light_color_temperature = color_temperature_mired_to_kelvin(
                color_temp
            )
        await super().async_turn_on(**kwargs)
