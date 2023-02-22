"""Light/LED support for the Skybell HD Doorbell."""
from __future__ import annotations

from typing import Any

from aioskybell.helpers.const import BRIGHTNESS, RGB_COLOR

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SkybellEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell switch."""
    async_add_entities(
        SkybellLight(coordinator, LightEntityDescription(key="light"))
        for coordinator in hass.data[DOMAIN][entry.entry_id]
    )


class SkybellLight(SkybellEntity, LightEntity):
    """A light implementation for Skybell devices."""

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_RGB_COLOR in kwargs:
            await self._device.async_set_setting(RGB_COLOR, kwargs[ATTR_RGB_COLOR])
        if ATTR_BRIGHTNESS in kwargs:
            level = int((kwargs.get(ATTR_BRIGHTNESS, 0) * 100) / 255)
            await self._device.async_set_setting(BRIGHTNESS, level)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._device.async_set_setting(ATTR_BRIGHTNESS, 0)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.led_intensity > 0

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return int((self._device.led_intensity * 255) / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._device.led_rgb
