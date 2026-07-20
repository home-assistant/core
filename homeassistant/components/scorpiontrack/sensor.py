"""Sensor platform for ScorpionTrack."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfSpeed
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
    """Set up ScorpionTrack speed sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ScorpionTrackSpeedSensor(coordinator, vehicle.id)
        for vehicle in coordinator.data.vehicles
    )


class ScorpionTrackSpeedSensor(ScorpionTrackEntity, SensorEntity):
    """Represent the latest shared vehicle speed."""

    _attr_device_class = SensorDeviceClass.SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_translation_key = "speed"

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
        if not super().available:
            return None
        return self.get_vehicle().position.speed_kmh

    @property
    @override
    def available(self) -> bool:
        """Return if the speed sensor is available."""
        return self._available_speed() is not None

    @property
    @override
    def native_value(self) -> float | None:
        """Return the speed in kilometres per hour."""
        return self._available_speed()
