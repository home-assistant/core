"""Binary sensor platform for ScorpionTrack."""

from collections.abc import Callable
from dataclasses import dataclass

from pyscorpiontrack import ScorpionTrackVehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator
from .entity import ScorpionTrackEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ScorpionTrackBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a ScorpionTrack binary sensor."""

    value_fn: Callable[[ScorpionTrackBinarySensorEntity, ScorpionTrackVehicle], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[ScorpionTrackBinarySensorEntityDescription, ...] = (
    ScorpionTrackBinarySensorEntityDescription(
        key="ignition",
        translation_key="ignition",
        value_fn=lambda entity, vehicle: vehicle.position.ignition is True,
    ),
    ScorpionTrackBinarySensorEntityDescription(
        key="location_stale",
        translation_key="location_stale",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entity, vehicle: entity.position_is_stale(vehicle),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ScorpionTrack binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        ScorpionTrackBinarySensorEntity(coordinator, vehicle.id, description)
        for vehicle in coordinator.data.vehicles
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class ScorpionTrackBinarySensorEntity(ScorpionTrackEntity, BinarySensorEntity):
    """Represent a vehicle-level ScorpionTrack binary sensor."""

    entity_description: ScorpionTrackBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ScorpionTrackCoordinator,
        vehicle_id: int,
        description: ScorpionTrackBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, vehicle_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        vehicle = self.get_vehicle()
        if vehicle is None:
            return None
        return self.entity_description.value_fn(self, vehicle)
