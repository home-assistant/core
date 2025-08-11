"""Support for Lutron Power Saver occupancy sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronData
from .aiolip import LIPGroupState, OccupancyGroup
from .entity import LutronBaseEntity, LutronControllerBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron binary_sensor platform.

    Adds occupancy groups from the Main Repeater associated with the
    config_entry as binary_sensor entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]

    # Add occupancy sensors
    entities: list[BinarySensorEntity] = [
        LutronOccupancySensor(device, entry_data.controller)
        for device in entry_data.binary_sensors
    ]

    # Add controller entity
    entities.append(LutronControllerConnectivitySensor(entry_data.controller))

    async_add_entities(entities, True)


class LutronOccupancySensor(LutronBaseEntity, BinarySensorEntity):
    """Representation of a Lutron Occupancy Group.

    The Lutron integration API reports "occupancy groups" rather than
    individual sensors. If two sensors are in the same room, they're
    reported as a single occupancy group.
    """

    _lutron_device: OccupancyGroup
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    async def _request_state(self):
        await self._execute_device_command(self._lutron_device.get_state)

    def _update_callback(self, value: int):
        """Handle group state update."""
        self._attr_is_on = (
            None if value == LIPGroupState.UNKNOWN else value == LIPGroupState.OCCUPIED
        )
        self.async_write_ha_state()


class LutronControllerConnectivitySensor(
    LutronControllerBaseEntity, BinarySensorEntity
):
    """Representation of the controller connection status."""

    _attr_should_poll = True
    _attr_name = "Connection Status"
    _attr_is_on = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._controller.guid} connection_status"

    async def async_update(self) -> None:
        """Periodically update the entity's status."""
        if self._controller:
            self._attr_is_on = self._controller.connected
        else:
            self._attr_is_on = False
