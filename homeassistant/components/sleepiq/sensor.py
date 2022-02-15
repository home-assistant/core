"""Support for SleepIQ Sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sleep numbers."""
    entry_id = discovery_info["email"]
    data = hass.data[DOMAIN][entry_id][SLEEPIQ_DATA]
    status_coordinator = hass.data[DOMAIN][entry_id][SLEEPIQ_STATUS_COORDINATOR]

    entities: list[SleepNumberSensorEntity] = []
    for bed in data.beds.values():
        for sleeper in bed.sleepers:
            entities.append(SleepNumberSensorEntity(sleeper, bed, status_coordinator))

    async_add_entities(entities)


class SleepNumberSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of an SleepIQ Entity with CoordinatorEntity."""

    _attr_icon = "mdi:gauge"

    def __init__(self, sleeper, bed, status_coordinator):
        """Initialize the sensor."""
        super().__init__(status_coordinator)
        self._sleeper = sleeper
        self._attr_name = f"SleepNumber {bed.name} {sleeper.name} SleepNumber"
        self._attr_unique_id = f"{bed.id}-{sleeper.side}-SN"

    @property
    def native_value(self) -> int:
        """Return the current sleep number value."""
        return self._sleeper.sleep_number
