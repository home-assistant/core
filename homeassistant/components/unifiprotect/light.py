"""This component provides Lights for UniFi Protect."""
from __future__ import annotations

import logging
from typing import Any

from pyunifiprotect.data import Light

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]
    entities = [
        ProtectLight(
            data,
            device,
        )
        for device in data.api.bootstrap.lights.values()
    ]

    if not entities:
        return

    async_add_entities(entities)


def unifi_brightness_to_hass(value: int) -> int:
    """Convert unifi brightness 1..6 to hass format 0..255."""
    return min(255, round((value / 6) * 255))


def hass_to_unifi_brightness(value: int) -> int:
    """Convert hass brightness 0..255 to unifi 1..6 scale."""
    return max(1, round((value / 255) * 6))


class ProtectLight(ProtectDeviceEntity, LightEntity):
    """A Ubiquiti UniFi Protect Light Entity."""

    device: Light

    _attr_icon = "mdi:spotlight-beam"
    _attr_supported_features = SUPPORT_BRIGHTNESS

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()
        self._attr_is_on = self.device.is_light_on
        self._attr_brightness = unifi_brightness_to_hass(
            self.device.light_device_settings.led_level
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        hass_brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        unifi_brightness = hass_to_unifi_brightness(hass_brightness)

        _LOGGER.debug("Turning on light with brightness %s", unifi_brightness)
        await self.device.set_light(True, unifi_brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug("Turning off light")
        await self.device.set_light(False)
