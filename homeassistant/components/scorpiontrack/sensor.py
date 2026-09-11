"""Sensor platform for ScorpionTrack."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pyscorpiontrack import ScorpionTrackShare, ScorpionTrackVehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, EntityCategory, UnitOfSpeed
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator
from .entity import ScorpionTrackEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ScorpionTrackSensorEntityDescription(SensorEntityDescription):
    """Describe a ScorpionTrack sensor."""

    value_fn: Callable[[ScorpionTrackVehicle], StateType | datetime]
    available_fn: Callable[[ScorpionTrackVehicle], bool] = lambda _: True
    suggested_unit_fn: Callable[[ScorpionTrackShare], str] | None = None


SENSORS: tuple[ScorpionTrackSensorEntityDescription, ...] = (
    ScorpionTrackSensorEntityDescription(
        key="heading",
        translation_key="heading",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda vehicle: vehicle.position.bearing,
    ),
    ScorpionTrackSensorEntityDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda vehicle: vehicle.position.speed_kmh,
        available_fn=lambda vehicle: vehicle.position.speed_kmh is not None,
        suggested_unit_fn=lambda share: (
            UnitOfSpeed.MILES_PER_HOUR
            if share.uses_miles
            else UnitOfSpeed.KILOMETERS_PER_HOUR
        ),
    ),
    ScorpionTrackSensorEntityDescription(
        key="last_reported",
        translation_key="last_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda vehicle: vehicle.position.timestamp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ScorpionTrack sensors."""
    coordinator = entry.runtime_data
    known_vehicles: set[int] = set()

    @callback
    def async_add_new_vehicles() -> None:
        """Add sensors for vehicles newly included in the share."""
        new_vehicles = coordinator.vehicles_by_id.keys() - known_vehicles
        if not new_vehicles:
            return
        known_vehicles.update(new_vehicles)
        async_add_entities(
            ScorpionTrackSensor(coordinator, vehicle_id, entity_description)
            for vehicle_id in new_vehicles
            for entity_description in SENSORS
        )

    async_add_new_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_vehicles))


class ScorpionTrackSensor(ScorpionTrackEntity, SensorEntity):
    """Represent a ScorpionTrack vehicle sensor."""

    entity_description: ScorpionTrackSensorEntityDescription

    def __init__(
        self,
        coordinator: ScorpionTrackCoordinator,
        vehicle_id: int,
        entity_description: ScorpionTrackSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle_id)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.data.id}_{vehicle_id}_{entity_description.key}"
        )
        if (suggested_unit_fn := entity_description.suggested_unit_fn) is not None:
            self._attr_suggested_unit_of_measurement = suggested_unit_fn(
                coordinator.data
            )

    @property
    @override
    def available(self) -> bool:
        """Return if the sensor is available."""
        return super().available and self.entity_description.available_fn(
            self.get_vehicle()
        )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.get_vehicle())
