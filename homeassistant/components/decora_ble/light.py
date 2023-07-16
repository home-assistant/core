"""Decora BLE integration light platform."""
from __future__ import annotations

from typing import Any, Optional

from decora_bleak import DecoraBLEDevice, DecoraBLEDeviceState, DecoraBLEDeviceSummary

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import DecoraBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform for Decora BLE."""
    data: DecoraBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DecoraBLEEntity(data.device, data.address, entry.title)])


class DecoraBLEEntity(LightEntity):
    """Representation of Decora BLE device."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, device: DecoraBLEDevice, address: str, name: str) -> None:
        """Initialize an Decora BLE light."""
        super().__init__()
        self._device = device
        self._attr_unique_id = address
        self._address = address

    @property
    def available(self) -> bool:
        """Determine if the entity is available."""
        return bool(self._device.is_connected)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness_level = self._to_device_brightness(kwargs.get(ATTR_BRIGHTNESS, None))
        await self._device.turn_on(brightness_level)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._device.turn_off()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            self._device.register_connection_callback(self._async_decora_connected)
        )
        self.async_on_remove(
            self._device.register_state_callback(self._async_decora_state_changed)
        )
        return await super().async_added_to_hass()

    @callback
    def _async_decora_connected(self, summary: DecoraBLEDeviceSummary) -> None:
        """Handle state changed."""
        self._attr_device_info = DeviceInfo(
            name=self._attr_name,
            manufacturer=summary.manufacturer,
            model=summary.model,
            sw_version=summary.software_revision,
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
        )

        self.schedule_update_ha_state()

    @callback
    def _async_decora_state_changed(self, state: DecoraBLEDeviceState) -> None:
        """Handle state changed."""
        self._attr_is_on = state.is_on
        self._attr_brightness = self._from_device_brightness(state.brightness_level)

        self.async_write_ha_state()

    def _from_device_brightness(self, brightness_level: int) -> int:
        return round((brightness_level / 100) * 255)

    def _to_device_brightness(self, brightness: Optional[int]) -> Optional[int]:
        if brightness is not None:
            return round((brightness / 255) * 100)
        return None
