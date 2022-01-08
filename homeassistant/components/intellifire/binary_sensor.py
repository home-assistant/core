"""Support for Intellifire Binary Sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntellifireDataUpdateCoordinator
from .const import DOMAIN

POWER = "on_off"
TIMER = "timer_on"
HOT = "is_hot"
THERMOSTAT = "thermostat_on"
FAN = "fan_on"
LIGHT = "light_on"
PILOT = "pilot_light_on"


INTELLIFIRE_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=POWER,  # This is the sensor name
        name="Power",  # This is the human readable name
        icon="mdi:power",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key=TIMER, name="Timer On", icon="mdi:camera-timer", device_class=None
    ),
    BinarySensorEntityDescription(
        key=PILOT, name="Pilot Light On", icon="mdi:fire-alert", device_class=None
    ),
    BinarySensorEntityDescription(
        key=THERMOSTAT,
        name="Thermostat On",
        icon="mdi:home-thermometer-outline",
        device_class=None,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Intellifire On/Off Sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        IntellifireBinarySensor(
            coordinator=coordinator, entry_id=entry.entry_id, description=description
        )
        for description in INTELLIFIRE_BINARY_SENSORS
    ]
    async_add_entities(entities)


class IntellifireBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A semi generic wrapper around Binary Sensor entiteis for Intellifire."""

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        entry_id,
        description: BinarySensorEntityDescription,
    ):
        """Class initializer."""
        super().__init__(coordinator)
        self.entity_description = description
        self.coordinator = coordinator
        self._entry_id = entry_id
        self._attrs: dict[str, Any] = {}

        # Set the Display name the User will see
        self._attr_name = f"{coordinator.intellifire_name} Fireplace {description.name}"
        self._attr_unique_id = f"Intellifire_{coordinator.serial}"

    @property
    def is_on(self):
        """Use this to get the correct value."""
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
