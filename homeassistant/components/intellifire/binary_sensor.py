from __future__ import annotations

from . import IntellifireDataUpdateCoordinator

"""Support for Intellifire Binary Sensors."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    HOT,
    INTELLIFIRE_BINARY_SENSORS,
    PILOT,
    POWER,
    THERMOSTAT,
    TIMER,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Intellifire On/Off Sensor"""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        IntellifireBinarySensor(
            coordinator=coordinator, entry_id=entry.entry_id, description=description
        )
        for description in INTELLIFIRE_BINARY_SENSORS
    ]
    async_add_entities(entities)


class IntellifireBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A semi generic wrapper around Binary Sensor entiteis for Intellifire"""

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        entry_id,
        description: BinarySensorEntityDescription,
    ):
        super().__init__(coordinator)
        self.entity_description = description
        self.coordinator = coordinator
        self._entry_id = entry_id
        self._attrs: dict[str, Any] = {}

        # Set the Dispaly name the User will see
        self._attr_name = f"{coordinator.intellifire_name} Fireplace {description.name}"
        self._attr_unique_id = (
            f"Intellifire_{coordinator.safe_intellifire_name}_{description.key}"
        )

    @property
    def is_on(self):
        sensor_type = self.entity_description.key
        if sensor_type == POWER:
            return self.coordinator.api.data.is_on
        if sensor_type == TIMER:
            return self.coordinator.api.data.timer_on
        if sensor_type == HOT:
            return self.coordinator.api.data.is_hot
        if sensor_type == THERMOSTAT:
            return self.coordinator.api.data.thermostat_on
        if sensor_type == PILOT:
            return self.coordinator.api.data.pilot_on
