"""Platform for FAA Delays sensor component."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FAA_BINARY_SENSORS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a FAA sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        FAABinarySensor(coordinator, entry.entry_id, description)
        for description in FAA_BINARY_SENSORS
    ]

    async_add_entities(entities)


class FAABinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Define a binary sensor for FAA Delays."""

    def __init__(
        self, coordinator, entry_id, description: BinarySensorEntityDescription
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self.coordinator = coordinator
        self._entry_id = entry_id
        self._attrs: dict[str, Any] = {}
        _id = coordinator.data.iata
        self._attr_name = f"{_id} {description.name}"
        self._attr_unique_id = f"{_id}_{description.key}"

    @property
    def is_on(self):
        """Return the status of the sensor."""
        sensor_type = self.entity_description.key
        if sensor_type == "GROUND_DELAY":
            return self.coordinator.data.ground_delay.status
        if sensor_type == "GROUND_STOP":
            return self.coordinator.data.ground_stop.status
        if sensor_type == "DEPART_DELAY":
            return self.coordinator.data.depart_delay.status
        if sensor_type == "ARRIVE_DELAY":
            return self.coordinator.data.arrive_delay.status
        if sensor_type == "CLOSURE":
            return self.coordinator.data.closure.status
        return None

    @property
    def extra_state_attributes(self):
        """Return attributes for sensor."""
        sensor_type = self.entity_description.key
        if sensor_type == "GROUND_DELAY":
            self._attrs["average"] = self.coordinator.data.ground_delay.average
            self._attrs["reason"] = self.coordinator.data.ground_delay.reason
        elif sensor_type == "GROUND_STOP":
            self._attrs["endtime"] = self.coordinator.data.ground_stop.endtime
            self._attrs["reason"] = self.coordinator.data.ground_stop.reason
        elif sensor_type == "DEPART_DELAY":
            self._attrs["minimum"] = self.coordinator.data.depart_delay.minimum
            self._attrs["maximum"] = self.coordinator.data.depart_delay.maximum
            self._attrs["trend"] = self.coordinator.data.depart_delay.trend
            self._attrs["reason"] = self.coordinator.data.depart_delay.reason
        elif sensor_type == "ARRIVE_DELAY":
            self._attrs["minimum"] = self.coordinator.data.arrive_delay.minimum
            self._attrs["maximum"] = self.coordinator.data.arrive_delay.maximum
            self._attrs["trend"] = self.coordinator.data.arrive_delay.trend
            self._attrs["reason"] = self.coordinator.data.arrive_delay.reason
        elif sensor_type == "CLOSURE":
            self._attrs["begin"] = self.coordinator.data.closure.begin
            self._attrs["end"] = self.coordinator.data.closure.end
            self._attrs["reason"] = self.coordinator.data.closure.reason
        return self._attrs
