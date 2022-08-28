"""Switchbot integration light platform."""
from __future__ import annotations

from typing import Any

from switchbot import ColorMode as SwitchBotColorMode, SwitchbotBulb

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .const import DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotSubscribeEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switchbot light."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SwitchbotBulbEntity(coordinator)])


class SwitchbotBulbEntity(SwitchbotSubscribeEntity, LightEntity):
    """Representation of switchbot Light bulb."""

    _device: SwitchbotBulb
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.RGB}

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        device = self._device
        self._attr_min_mireds = color_temperature_kelvin_to_mired(device.max_temp)
        self._attr_max_mireds = color_temperature_kelvin_to_mired(device.min_temp)
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        device = self._device
        self._attr_is_on = self._device.on
        self._attr_brightness = max(0, min(255, round(device.brightness * 2.55)))
        if device.color_mode == SwitchBotColorMode.COLOR_TEMP:
            self._attr_color_temp = color_temperature_kelvin_to_mired(device.color_temp)
            self._attr_color_mode = ColorMode.COLOR_TEMP
            return
        self._attr_rgb_color = device.rgb
        self._attr_color_mode = ColorMode.RGB

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness = round(kwargs.get(ATTR_BRIGHTNESS, self.brightness) / 255 * 100)

        if ATTR_COLOR_TEMP in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP]
            kelvin = max(2700, min(6500, color_temperature_mired_to_kelvin(color_temp)))
            await self._device.set_color_temp(brightness, kelvin)
            return
        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            await self._device.set_rgb(brightness, rgb[0], rgb[1], rgb[2])
            return
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.set_brightness(brightness)
            return
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._device.turn_off()
