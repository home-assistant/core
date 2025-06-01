"""Binary sensor platform for Grid Connect."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Grid Connect binary sensor platform."""
    coordinator: DataUpdateCoordinator[Any] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GridConnectBinarySensor(coordinator)])


class GridConnectBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[Any]], BinarySensorEntity
):
    """Representation of a Grid Connect binary sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator[Any]) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_name = "Grid Connect Sensor"
        self._attr_device_class = BinarySensorDeviceClass.MOTION
        _LOGGER.debug("Initialized Grid Connect binary sensor")

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        sensor_state: bool | None = self.coordinator.data.get("sensor_state")
        if sensor_state is None:
            _LOGGER.debug("Sensor state is unknown, returning None")
            return None
        is_sensor_on = bool(sensor_state)
        _LOGGER.debug("Sensor state is %s, returning %s", sensor_state, is_sensor_on)
        return is_sensor_on
