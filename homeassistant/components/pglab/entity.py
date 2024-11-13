"""Entity for PG LAB Electronics."""

from __future__ import annotations

from pypglab.device import Device as PyPGLabDevice
from pypglab.entity import Entity as PyPGLabEntity

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .discovery import PGLabDiscovery


class PGLabEntity(Entity):
    """Representation of a PGLab entity in Home Assistant."""

    _attr_has_entity_name = True

    def __init__(
        self,
        discovery: PGLabDiscovery,
        device: PyPGLabDevice,
        entity: PyPGLabEntity,
    ) -> None:
        """Initialize the class."""

        self._id = entity.id
        self._device_id = device.id
        self._entity = entity
        self._discovery = discovery

        # Information about the device that is partially visible in the UI.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
            model=device.type,
            manufacturer=device.manufactor,
            configuration_url=f"http://{device.ip}/",
            connections={(CONNECTION_NETWORK_MAC, device.mac)},
        )

    async def async_added_to_hass(self) -> None:
        """Update the device discovery info."""

        self._entity.set_on_state_callback(self.state_updated)
        await self._entity.subscribe_topics()

        await super().async_added_to_hass()

        # Inform PGLab discovery instance that a new entity is available.
        # This is important to know in case the device needs to be reconfigured
        # and the entity can be potentially destroyed.
        await self._discovery.add_entity(self, self._device_id)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""

        await super().async_will_remove_from_hass()

        await self._entity.unsubscribe_topics()
        self._entity.set_on_state_callback(None)

    @callback
    def state_updated(self, payload: str) -> None:
        """Handle state updates."""
        self.async_write_ha_state()
