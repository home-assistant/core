"""The SenseME integration entities."""
from __future__ import annotations

from aiosenseme import SensemeDevice

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity


class SensemeEntity(Entity):
    """Base class for senseme entities."""

    _attr_should_poll = False

    def __init__(self, device: SensemeDevice, name: str) -> None:
        """Initialize the entity."""
        self._device = device
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
            name=self._device.name,
            manufacturer="Big Ass Fans",
            model=self._device.model,
            sw_version=self._device.fw_version,
            suggested_area=self._device.room_name,
        )
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_available = self._device.available

    @callback
    def _async_update_from_device(self) -> None:
        """Process an update from the device."""
        self._async_update_attrs()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        self._device.add_callback(self._async_update_from_device)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        self._device.remove_callback(self._async_update_from_device)
