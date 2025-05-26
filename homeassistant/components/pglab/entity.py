"""Entity for PG LAB Electronics."""

from __future__ import annotations

from pypglab.device import Device as PyPGLabDevice
from pypglab.entity import Entity as PyPGLabEntity

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PGLabSensorsCoordinator
from .discovery import PGLabDiscovery


class PGLabBaseEntity(Entity):
    """Base class of a PGLab entity in Home Assistant."""

    _attr_has_entity_name = True

    def __init__(
        self,
        pglab_discovery: PGLabDiscovery,
        pglab_device: PyPGLabDevice,
    ) -> None:
        """Initialize the class."""

        self._device_id = pglab_device.id
        self._discovery = pglab_discovery

        # Information about the device that is partially visible in the UI.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pglab_device.id)},
            name=pglab_device.name,
            sw_version=pglab_device.firmware_version,
            hw_version=pglab_device.hardware_version,
            model=pglab_device.type,
            manufacturer=pglab_device.manufacturer,
            configuration_url=f"http://{pglab_device.ip}/",
            connections={(CONNECTION_NETWORK_MAC, pglab_device.mac)},
        )

    async def async_added_to_hass(self) -> None:
        """Update the device discovery info."""

        # Inform PGLab discovery instance that a new entity is available.
        # This is important to know in case the device needs to be reconfigured
        # and the entity can be potentially destroyed.
        await self._discovery.add_entity(
            self.platform.domain,
            self.unique_id,
            self._device_id,
        )

        # propagate the async_added_to_hass to the super class
        await super().async_added_to_hass()


class PGLabEntity(PGLabBaseEntity):
    """Representation of a PGLab entity in Home Assistant."""

    def __init__(
        self,
        pglab_discovery: PGLabDiscovery,
        pglab_device: PyPGLabDevice,
        pglab_entity: PyPGLabEntity,
    ) -> None:
        """Initialize the class."""

        super().__init__(pglab_discovery, pglab_device)

        self._id = pglab_entity.id
        self._entity: PyPGLabEntity = pglab_entity

    async def async_added_to_hass(self) -> None:
        """Subscribe pypglab entity to be updated from mqtt when pypglab entity internal state change."""

        # set the callback to be called when pypglab entity state is changed
        self._entity.set_on_state_callback(self.state_updated)

        # subscribe to the pypglab entity to receive updates from the mqtt broker
        await self._entity.subscribe_topics()
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""

        await super().async_will_remove_from_hass()
        await self._entity.unsubscribe_topics()
        self._entity.set_on_state_callback(None)

    @callback
    def state_updated(self, payload: str) -> None:
        """Handle state updates."""
        self.async_write_ha_state()


class PGLabSensorEntity(PGLabBaseEntity, CoordinatorEntity[PGLabSensorsCoordinator]):
    """Representation of a PGLab sensor entity in Home Assistant."""

    def __init__(
        self,
        pglab_discovery: PGLabDiscovery,
        pglab_device: PyPGLabDevice,
        pglab_coordinator: PGLabSensorsCoordinator,
    ) -> None:
        """Initialize the class."""

        PGLabBaseEntity.__init__(self, pglab_discovery, pglab_device)
        CoordinatorEntity.__init__(self, pglab_coordinator)
