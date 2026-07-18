"""Sensor platform for ScorpionTrack."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pyscorpiontrack import ScorpionTrackVehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, EntityCategory, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator
from .entity import ScorpionTrackEntity

PARALLEL_UPDATES = 0

type ScorpionTrackSensorValue = StateType | datetime


@dataclass(frozen=True, kw_only=True)
class ScorpionTrackSensorEntityDescription(SensorEntityDescription):
    """Describe a ScorpionTrack sensor entity."""

    value_fn: Callable[[ScorpionTrackVehicle], ScorpionTrackSensorValue]


SENSOR_DESCRIPTIONS: tuple[ScorpionTrackSensorEntityDescription, ...] = (
    ScorpionTrackSensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda vehicle: vehicle.position.speed_kmh,
    ),
    ScorpionTrackSensorEntityDescription(
        key="last_reported",
        translation_key="last_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda vehicle: vehicle.position.timestamp,
    ),
    ScorpionTrackSensorEntityDescription(
        key="heading",
        translation_key="heading",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda vehicle: vehicle.position.bearing,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ScorpionTrack sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        ScorpionTrackSensorEntity(coordinator, vehicle.id, description)
        for vehicle in coordinator.data.vehicles
        for description in SENSOR_DESCRIPTIONS
    )


class ScorpionTrackSensorEntity(ScorpionTrackEntity, SensorEntity):
    """Represent a ScorpionTrack vehicle sensor."""

    entity_description: ScorpionTrackSensorEntityDescription

    def __init__(
        self,
        coordinator: ScorpionTrackCoordinator,
        vehicle_id: int,
        description: ScorpionTrackSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_{description.key}"
        if description.key == "speed":
            self._attr_suggested_unit_of_measurement = (
                UnitOfSpeed.MILES_PER_HOUR
                if coordinator.data.uses_miles
                else UnitOfSpeed.KILOMETERS_PER_HOUR
            )

    def _available_value(self) -> ScorpionTrackSensorValue:
        """Return the current value when its vehicle is available."""
        if not super().available:
            return None
        return self.entity_description.value_fn(self.get_vehicle())

    @property
    @override
    def available(self) -> bool:
        """Return if the sensor value is available."""
        return self._available_value() is not None

    @property
    @override
    def native_value(self) -> ScorpionTrackSensorValue:
        """Return the sensor value from the coordinator snapshot."""
        return self._available_value()
