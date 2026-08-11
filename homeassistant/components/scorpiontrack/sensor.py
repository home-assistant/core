"""Sensor platform for ScorpionTrack."""

from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator
from .entity import ScorpionTrackEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ScorpionTrack sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        sensor
        for vehicle in coordinator.data.vehicles
        for sensor in (
            ScorpionTrackSpeedSensor(coordinator, vehicle.id),
            ScorpionTrackLastReportedSensor(coordinator, vehicle.id),
        )
    )


class ScorpionTrackSpeedSensor(ScorpionTrackEntity, SensorEntity):
    """Represent the latest shared vehicle speed."""

    _attr_device_class = SensorDeviceClass.SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the speed sensor."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_speed"
        self._attr_suggested_unit_of_measurement = (
            UnitOfSpeed.MILES_PER_HOUR
            if coordinator.data.uses_miles
            else UnitOfSpeed.KILOMETERS_PER_HOUR
        )

    def _available_speed(self) -> float | None:
        """Return the speed if the sensor is available."""
        return self.get_vehicle().position.speed_kmh

    @property
    @override
    def available(self) -> bool:
        """Return if the speed sensor is available."""
        return super().available and self._available_speed() is not None

    @property
    @override
    def native_value(self) -> float | None:
        """Return the speed in kilometres per hour."""
        return self._available_speed()


class ScorpionTrackLastReportedSensor(ScorpionTrackEntity, SensorEntity):
    """Represent when the vehicle last reported its position."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_reported"

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the last reported sensor."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_last_reported"

    def _available_timestamp(self) -> datetime | None:
        """Return the timestamp if the sensor is available."""
        return self.get_vehicle().position.timestamp

    @property
    @override
    def available(self) -> bool:
        """Return if the last reported sensor is available."""
        return super().available and self._available_timestamp() is not None

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return when the vehicle last reported."""
        return self._available_timestamp()
