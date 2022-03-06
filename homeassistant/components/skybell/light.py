"""Light/LED support for the Skybell HD Doorbell."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_HS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from . import SkybellEntity
from .const import DOMAIN
from .coordinator import SkybellDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell switch."""
    async_add_entities(
        SkybellLight(coordinator)
        for coordinator in hass.data[DOMAIN][entry.entry_id].values()
    )


class SkybellLight(SkybellEntity, LightEntity):
    """A light implementation for Skybell devices."""

    _attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS, COLOR_MODE_HS}
    coordinator: SkybellDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SkybellDataUpdateCoordinator,
    ) -> None:
        """Initialize a light for a Skybell device."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.name}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            await self.coordinator.device.async_set_setting(ATTR_HS_COLOR, rgb)
        elif ATTR_BRIGHTNESS in kwargs:
            level = int((kwargs[ATTR_BRIGHTNESS] * 100) / 255)
            await self.coordinator.device.async_set_setting(ATTR_BRIGHTNESS, level)
        else:
            await self.coordinator.device.async_set_setting(ATTR_BRIGHTNESS, 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.device.async_set_setting(ATTR_BRIGHTNESS, 0)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.coordinator.device.led_intensity > 0

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return int((self.coordinator.device.led_intensity * 255) / 100)

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the color of the light."""
        return color_util.color_RGB_to_hs(*self.coordinator.device.led_rgb)
