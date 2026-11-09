"""Device tracker platform for the A Better Routeplanner integration."""

from typing import override

from aioabrp import Location, MetricValue

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
        for raw, _ in runtime.garage_coordinator.data:
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
    _last_report: tuple[MetricValue[Location] | None, bool] | None = None

    def _report(self) -> tuple[MetricValue[Location] | None, bool]:
        tlm = self.telemetry
        return (
            tlm.location if tlm is not None else None,
            self.coordinator.stream_auth_failed,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Remember the report written when the entity is added."""
        await super().async_added_to_hass()
        self._last_report = self._report()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Write only on a new position report or an availability change.

        TrackerEntity forces every write, but the shared coordinator notifies
        on every frame of every metric for every vehicle, so writing each one
        would bump last_updated without a new position. A new report carries
        a new timestamp; a reconnect replays the last one with its original
        timestamp and is skipped.
        """
        if (report := self._report()) != self._last_report:
            self._last_report = report
            super()._handle_coordinator_update()

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
