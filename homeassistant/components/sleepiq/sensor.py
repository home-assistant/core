"""Support for SleepIQ Sensor."""
from __future__ import annotations

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PRESSURE, SLEEP_NUMBER
from .coordinator import SleepIQData
from .entity import SleepIQSensor

SENSORS = [PRESSURE, SLEEP_NUMBER]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SleepIQSensorEntity(data.data_coordinator, bed, sleeper, sensor_type)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for sensor_type in SENSORS
    )


class SleepIQSensorEntity(SleepIQSleeperEntity, SensorEntity):
    """Representation of an SleepIQ Entity with CoordinatorEntity."""

    _attr_icon = "mdi:bed"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        self.sensor_type = sensor_type
        super().__init__(coordinator, bed, sleeper, sensor_type)

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = getattr(self.sleeper, self.sensor_type)
