"""Entity for PG LAB Electronics."""
from __future__ import annotations

from pypglab.device import Device
from pypglab.entity import Entity

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity as HA_Entity

from .const import DEVICE_ALREADY_DISCOVERED, DOMAIN


class BaseEntity(HA_Entity):
    """Representation of a PGLAB entity in Home Assistant."""

    def __init__(self, platform: str, device: Device, entity: Entity) -> None:
        """Initialize the class."""

        super().__init__()

        self._id = entity.id
        self._device_id = device.id
        self._entity = entity

        # Set the state update
        self._entity.add_state_update(self.state_updated)

        # Information about the devices that is partially visible in the UI.
        self._attr_device_info = DeviceInfo(
            {
                "identifiers": {(DOMAIN, device.id)},
                # If desired, the name for the device could be different to the entity
                "name": device.name,
                "sw_version": device.firmware_version,
                "hw_version": device.hardware_version,
                "model": device.type,
                "manufacturer": device.manufactor,
                "configuration_url": f"http://{device.ip}/",
                "connections": {(CONNECTION_NETWORK_MAC, device.mac)},
            }
        )

    async def async_added_to_hass(self) -> None:
        """Update the device discovery info."""
        discovery_info = self.hass.data[DEVICE_ALREADY_DISCOVERED][self._device_id]
        discovery_info.add_entity(self)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""
        await self._entity.unsubscribe_topics()

    @callback
    def state_updated(self, payload: str) -> None:
        """Handle state updates."""
        self.async_write_ha_state()
