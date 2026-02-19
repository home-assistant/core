"""Component providing Lights for UniFi Protect."""

from __future__ import annotations

import logging
from typing import Any

from uiprotect.data import Light, ModelType, ProtectAdoptableDeviceModel
from uiprotect.data.devices import LightDeviceSettings

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity
from .utils import async_ufp_instance_command

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    @async_ufp_instance_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        led_level: int | None = None
        if brightness is not None:
            led_level = hass_to_unifi_brightness(brightness)
            _LOGGER.debug(
                "Turning on light with brightness %s (led_level=%s)",
                brightness,
                led_level,
            )
        else:
            _LOGGER.debug("Turning on light")

        await self.device.api.update_light_public(
            self.device.id,
            is_light_force_enabled=True,
            light_device_settings=(
                LightDeviceSettings(
                    is_indicator_enabled=self.device.light_device_settings.is_indicator_enabled,
                    led_level=led_level,
                    pir_duration=self.device.light_device_settings.pir_duration,
                    pir_sensitivity=self.device.light_device_settings.pir_sensitivity,
                )
                if led_level is not None
                else None
            ),
        )

    @async_ufp_instance_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug("Turning off light")
        await self.device.api.update_light_public(
            self.device.id, is_light_force_enabled=False
        )
