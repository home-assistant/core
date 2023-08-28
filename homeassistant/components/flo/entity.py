"""Base entity class for Flo entities."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDeviceDataUpdateCoordinator


class FloEntity(Entity):
    """A base class for Flo entities."""

    _attr_force_update = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entity_type: str,
        device: FloDeviceDataUpdateCoordinator,
        **kwargs,
    ) -> None:
        """Init Flo entity."""
        self._attr_unique_id = f"{device.mac_address}_{entity_type}"

        self._device: FloDeviceDataUpdateCoordinator = device
        self._state: Any = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._device.mac_address)},
            identifiers={(FLO_DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            name=self._device.device_name.capitalize(),
            sw_version=self._device.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._device.available

    async def async_update(self):
        """Update Flo entity."""
        await self._device.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._device.async_add_listener(self.async_write_ha_state))
