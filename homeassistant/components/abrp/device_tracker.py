"""Device tracker platform for the A Better Routeplanner integration."""

from typing import override

from aioabrp import Location

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AbrpConfigEntry
from .entity import AbrpVehicleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbrpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a tracker for every garage vehicle that reports a position."""
    runtime = entry.runtime_data
    telemetry_coordinator = runtime.telemetry_coordinator

    added: set[int] = set()

    @callback
    def _add_new_trackers() -> None:
        entities: list[AbrpDeviceTracker] = []
        for raw, _ in runtime.vehicles:
            vehicle_id = raw.vehicle_id
            if vehicle_id in added:
                continue
            tlm = telemetry_coordinator.data.get(vehicle_id)
            if tlm is None or tlm.location is None:
                continue
            entities.append(
                AbrpDeviceTracker(telemetry_coordinator, entry, vehicle_id, "location")
            )
            added.add(vehicle_id)
        async_add_entities(entities)

    entry.async_on_unload(telemetry_coordinator.async_add_listener(_add_new_trackers))
    _add_new_trackers()


class AbrpDeviceTracker(AbrpVehicleEntity, TrackerEntity):
    """GPS position of one vehicle."""

    _attr_translation_key = "location"

    @property
    @override
    def force_update(self) -> bool:
        """Skip unchanged positions; last_reported records repeated reports."""
        return False

    @property
    def _location(self) -> Location | None:
        tlm = self.telemetry
        metric = tlm.location if tlm is not None else None
        return metric.value if metric is not None else None

    @property
    @override
    def latitude(self) -> float | None:
        """Return the latest latitude."""
        return location.lat if (location := self._location) is not None else None

    @property
    @override
    def longitude(self) -> float | None:
        """Return the latest longitude."""
        return location.lon if (location := self._location) is not None else None

    @property
    @override
    def available(self) -> bool:
        """Unavailable without a position or after stream auth failure."""
        return not self.coordinator.stream_auth_failed and self._location is not None
