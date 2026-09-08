"""Binary sensor platform for ScorpionTrack."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
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
    entity_registry = er.async_get(hass)
    known_vehicles: set[int] = set()

    @callback
    def async_add_new_vehicles() -> None:
        """Add ignition sensors for vehicles newly included in the share."""
        new_vehicles = {
            vehicle_id
            for vehicle_id in coordinator.vehicles_by_id
            if vehicle_id not in known_vehicles
            or entity_registry.async_get_entity_id(
                "binary_sensor", DOMAIN, f"{coordinator.data.id}_{vehicle_id}_ignition"
            )
            is None
        }
        if not new_vehicles:
            return
        known_vehicles.update(new_vehicles)
        async_add_entities(
            ScorpionTrackIgnitionBinarySensor(coordinator, vehicle_id)
            for vehicle_id in new_vehicles
        )

    async_add_new_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_vehicles))


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
