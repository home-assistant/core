"""Support for SleepIQ Sensor."""

from __future__ import annotations

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PRESSURE, SLEEP_NUMBER
from .coordinator import SleepIQData, SleepIQDataUpdateCoordinator
from .entity import SleepIQSleeperEntity

SENSORS = [PRESSURE, SLEEP_NUMBER]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SleepIQSensorEntity(data.data_coordinator, bed, sleeper, sensor_type)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for sensor_type in SENSORS
    )


class SleepIQSensorEntity(
    SleepIQSleeperEntity[SleepIQDataUpdateCoordinator], SensorEntity
):
    """Representation of an SleepIQ Entity with CoordinatorEntity."""

    _attr_icon = "mdi:bed"

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        self.sensor_type = sensor_type
        self._attr_state_class = SensorStateClass.MEASUREMENT
        super().__init__(coordinator, bed, sleeper, sensor_type)

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = getattr(self.sleeper, self.sensor_type)
