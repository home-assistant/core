"""Binary sensor platform for ScorpionTrack."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up ScorpionTrack ignition binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ScorpionTrackIgnitionBinarySensor(coordinator, vehicle.id)
        for vehicle in coordinator.data.vehicles
    )


class ScorpionTrackIgnitionBinarySensor(ScorpionTrackEntity, BinarySensorEntity):
    """Represent the latest shared vehicle ignition state."""

    _attr_translation_key = "ignition"

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the ignition binary sensor."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_ignition"

    def _available_ignition(self) -> bool | None:
        """Return the ignition value."""
        return self.get_vehicle().position.ignition

    @property
    @override
    def available(self) -> bool:
        """Return if the ignition binary sensor is available."""
        return super().available and self._available_ignition() is not None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the ignition state."""
        return self._available_ignition()
