"""Sensor platform for ScorpionTrack."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pyscorpiontrack import ScorpionTrackShare, ScorpionTrackVehicle

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
from .entity import ScorpionTrackEntity, ScorpionTrackShareEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ScorpionTrackVehicleSensorEntityDescription(SensorEntityDescription):
    """Describe a vehicle-level ScorpionTrack sensor."""

    value_fn: Callable[[ScorpionTrackShare, ScorpionTrackVehicle], StateType | datetime]
    unit_fn: Callable[[ScorpionTrackShare], str | None] | None = None


@dataclass(frozen=True, kw_only=True)
class ScorpionTrackShareSensorEntityDescription(SensorEntityDescription):
    """Describe a share-level ScorpionTrack sensor."""

    value_fn: Callable[[ScorpionTrackShare], StateType | datetime]


VEHICLE_SENSOR_DESCRIPTIONS: tuple[ScorpionTrackVehicleSensorEntityDescription, ...] = (
    ScorpionTrackVehicleSensorEntityDescription(
        key="status",
        translation_key="status",
        value_fn=lambda share, vehicle: vehicle.status,
    ),
    ScorpionTrackVehicleSensorEntityDescription(
        key="location",
        translation_key="location",
        value_fn=lambda share, vehicle: _format_location(vehicle),
    ),
    ScorpionTrackVehicleSensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda share, vehicle: share.convert_speed(vehicle.position.speed_kmh),
        unit_fn=lambda share: (
            UnitOfSpeed.MILES_PER_HOUR
            if share.uses_miles
            else UnitOfSpeed.KILOMETERS_PER_HOUR
        ),
    ),
    ScorpionTrackVehicleSensorEntityDescription(
        key="heading",
        translation_key="heading",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        value_fn=lambda share, vehicle: (
            round(vehicle.position.bearing)
            if vehicle.position.bearing is not None
            else None
        ),
    ),
    ScorpionTrackVehicleSensorEntityDescription(
        key="last_reported",
        translation_key="last_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda share, vehicle: vehicle.position.timestamp,
    ),
)

SHARE_SENSOR_DESCRIPTIONS: tuple[ScorpionTrackShareSensorEntityDescription, ...] = (
    ScorpionTrackShareSensorEntityDescription(
        key="share_title",
        translation_key="share_title",
        value_fn=lambda share: share.title,
    ),
    ScorpionTrackShareSensorEntityDescription(
        key="shared_by",
        translation_key="shared_by",
        value_fn=lambda share: share.owner_name,
    ),
    ScorpionTrackShareSensorEntityDescription(
        key="share_created",
        translation_key="share_created",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda share: share.created_at,
    ),
    ScorpionTrackShareSensorEntityDescription(
        key="share_expires",
        translation_key="share_expires",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda share: share.expires_at,
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
        [
            *(
                ScorpionTrackShareSensorEntity(coordinator, description)
                for description in SHARE_SENSOR_DESCRIPTIONS
            ),
            *(
                ScorpionTrackVehicleSensorEntity(coordinator, vehicle.id, description)
                for vehicle in coordinator.data.vehicles
                for description in VEHICLE_SENSOR_DESCRIPTIONS
            ),
        ]
    )


class ScorpionTrackVehicleSensorEntity(ScorpionTrackEntity, SensorEntity):
    """Represent a vehicle-level ScorpionTrack sensor."""

    entity_description: ScorpionTrackVehicleSensorEntityDescription

    def __init__(
        self,
        coordinator: ScorpionTrackCoordinator,
        vehicle_id: int,
        description: ScorpionTrackVehicleSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native sensor value."""
        vehicle = self.get_vehicle()
        if vehicle is None:
            return None
        return self.entity_description.value_fn(self.share, vehicle)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        if self.entity_description.unit_fn is None:
            return self.entity_description.native_unit_of_measurement
        return self.entity_description.unit_fn(self.share)


class ScorpionTrackShareSensorEntity(ScorpionTrackShareEntity, SensorEntity):
    """Represent a share-level ScorpionTrack sensor."""

    entity_description: ScorpionTrackShareSensorEntityDescription

    def __init__(
        self,
        coordinator: ScorpionTrackCoordinator,
        description: ScorpionTrackShareSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.id}_share_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native sensor value."""
        return self.entity_description.value_fn(self.share)


def _format_location(vehicle: ScorpionTrackVehicle) -> str | None:
    """Return a human-friendly location string."""
    if vehicle.position.address:
        return vehicle.position.address
    if vehicle.position.latitude is not None and vehicle.position.longitude is not None:
        return f"{vehicle.position.latitude:.6f}, {vehicle.position.longitude:.6f}"
    return None
