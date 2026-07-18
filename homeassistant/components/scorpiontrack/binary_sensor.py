"""Binary sensor platform for ScorpionTrack."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator
from .entity import ScorpionTrackEntity

PARALLEL_UPDATES = 0

IGNITION_DESCRIPTION = BinarySensorEntityDescription(
    key="ignition",
    translation_key="ignition",
    device_class=BinarySensorDeviceClass.RUNNING,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ScorpionTrack ignition entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        ScorpionTrackIgnitionEntity(coordinator, vehicle.id)
        for vehicle in coordinator.data.vehicles
    )


class ScorpionTrackIgnitionEntity(ScorpionTrackEntity, BinarySensorEntity):
    """Represent a ScorpionTrack vehicle ignition state."""

    entity_description = IGNITION_DESCRIPTION

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the ignition entity."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_ignition"

    def _available_ignition(self) -> bool | None:
        """Return ignition when its vehicle is available."""
        if not super().available:
            return None
        return self.get_vehicle().position.ignition

    @property
    @override
    def available(self) -> bool:
        """Return if the ignition value is available."""
        return self._available_ignition() is not None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return ignition from the coordinator snapshot."""
        return self._available_ignition()
