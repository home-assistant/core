"""Support for Eight Sleep binary sensors."""
from __future__ import annotations

import logging

from pyeight.eight import EightSleep

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import EightSleepBaseEntity, EightSleepConfigEntryData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
BINARY_SENSORS = ["bed_presence"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the eight sleep binary sensor."""
    config_entry_data: EightSleepConfigEntryData = hass.data[DOMAIN][entry.entry_id]
    eight = config_entry_data.api
    heat_coordinator = config_entry_data.heat_coordinator
    async_add_entities(
        EightHeatSensor(entry, heat_coordinator, eight, user.user_id, binary_sensor)
        for user in eight.users.values()
        for binary_sensor in BINARY_SENSORS
    )


class EightHeatSensor(EightSleepBaseEntity, BinarySensorEntity):
    """Representation of a Eight Sleep heat-based sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        eight: EightSleep,
        user_id: str | None,
        sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry, coordinator, eight, user_id, sensor)
        assert self._user_obj
        _LOGGER.debug(
            "Presence Sensor: %s, Side: %s, User: %s",
            sensor,
            self._user_obj.side,
            user_id,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        assert self._user_obj
        return bool(self._user_obj.bed_presence)
