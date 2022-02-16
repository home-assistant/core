"""Support for SleepIQ Sensor."""
from __future__ import annotations

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SLEEP_NUMBER, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR
from .entity import SleepIQSensor

ICON = "mdi:bed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        SLEEPIQ_STATUS_COORDINATOR
    ]
    data = hass.data[DOMAIN][entry.entry_id][SLEEPIQ_DATA]
    entities: list[SleepNumberSensorEntity] = []
    for bed in data.beds.values():
        for sleeper in bed.sleepers:
            entities.append(SleepNumberSensorEntity(coordinator, bed, sleeper))

    async_add_entities(entities)


class SleepNumberSensorEntity(SleepIQSensor, SensorEntity):
    """Representation of an SleepIQ Entity with CoordinatorEntity."""

    _attr_icon = ICON

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, bed, sleeper, SLEEP_NUMBER)

    @property
    def native_value(self) -> int:
        """Return the current sleep number value."""
        return int(self.sleeper.sleep_number)
