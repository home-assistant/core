"""Support for SleepIQ Sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR
from .device import SleepNumberCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sleep numbers."""
    data = hass.data[DOMAIN][config_entry.entry_id][SLEEPIQ_DATA]
    status_coordinator = hass.data[DOMAIN][config_entry.entry_id][
        SLEEPIQ_STATUS_COORDINATOR
    ]

    entities: list[SleepNumberSensorEntity] = []
    for bed in data.beds.values():
        for sleeper in bed.sleepers:
            entities.append(SleepNumberSensorEntity(sleeper, bed, status_coordinator))

    async_add_entities(entities)


class SleepNumberSensorEntity(SleepNumberCoordinatorEntity, SensorEntity):
    """Representation of a sleep number."""

    _attr_icon = "mdi:gauge"

    def __init__(self, sleeper, bed, status_coordinator):
        super().__init__(bed, status_coordinator)
        self._sleeper = sleeper
        self._attr_name = f"{sleeper.name} Sleep Number"
        self._attr_unique_id = f"{bed.id}-{sleeper.side}-SN"

    @property
    def native_value(self) -> int:
        """Return the current sleep number value."""
        return self._sleeper.sleep_number
