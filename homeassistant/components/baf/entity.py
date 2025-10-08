"""The baf integration entities."""

from __future__ import annotations

from aiobafi6 import Device

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity, EntityDescription


class BAFEntity(Entity):
    """Base class for baf entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        """Initialize the entity."""
        self._device = device
        self._attr_unique_id = format_mac(self._device.mac_address)
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac_address)},
            name=self._device.name,
            manufacturer="Big Ass Fans",
            model=self._device.model,
            sw_version=self._device.firmware_version,
        )
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_available = self._device.available

    @callback
    def _async_update_from_device(self, device: Device) -> None:
        """Process an update from the device."""
        self._async_update_attrs()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        self._device.add_callback(self._async_update_from_device)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        self._device.remove_callback(self._async_update_from_device)


class BAFDescriptionEntity(BAFEntity):
    """Base class for baf entities that use an entity description."""

    def __init__(self, device: Device, description: EntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device)
        self._attr_unique_id = f"{device.mac_address}-{description.key}"
