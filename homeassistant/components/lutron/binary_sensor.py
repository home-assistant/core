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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronDevice

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
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}

    def _update_attrs(self) -> None:
        """Update the state attributes."""
        self._attr_is_on = self._lutron_device.state == OccupancyGroup.State.OCCUPIED
