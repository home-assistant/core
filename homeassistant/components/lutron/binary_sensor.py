"""Support for Lutron Powr Savr occupancy sensors."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pylutron import OccupancyGroup

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron binary_sensor platform.

    Adds occupancy groups from the Main Repeater associated with the
    config_entry as binary_sensor entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            LutronOccupancySensor(area_name, device, entry_data.client)
            for area_name, device in entry_data.binary_sensors
        ],
        True,
    )


class LutronOccupancySensor(LutronDevice, BinarySensorEntity):
    """Representation of a Lutron Occupancy Group.

    The Lutron integration API reports "occupancy groups" rather than
    individual sensors. If two sensors are in the same room, they're
    reported as a single occupancy group.
    """

    _lutron_device: OccupancyGroup
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        # Error cases will end up treated as unoccupied.
        return self._lutron_device.state == OccupancyGroup.State.OCCUPIED

    @property
    def name(self) -> str:
        """Return the name of the device."""
        # The default LutronDevice naming would create 'Kitchen Occ Kitchen',
        # but since there can only be one OccupancyGroup per area we go
        # with something shorter.
        return f"{self._area_name} Occupancy"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
