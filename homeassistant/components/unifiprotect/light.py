"""Component providing Lights for UniFi Protect."""

from __future__ import annotations

import logging
from typing import Any

from uiprotect.data import Light, ModelType, ProtectAdoptableDeviceModel

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if device.model is ModelType.LIGHT and device.can_write(
            data.api.bootstrap.auth_user
        ):
            async_add_entities([ProtectLight(data, device)])

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(
        ProtectLight(data, device)
        for device in data.get_by_types({ModelType.LIGHT})
        if device.can_write(data.api.bootstrap.auth_user)
    )


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
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _state_attrs = ("_attr_available", "_attr_is_on", "_attr_brightness")

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        updated_device = self.device
        self._attr_is_on = updated_device.is_light_on
        self._attr_brightness = unifi_brightness_to_hass(
            updated_device.light_device_settings.led_level
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
