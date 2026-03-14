"""Platform for GPS device tracker integration.

Reads position data from PajGpsCoordinator and exposes it as a TrackerEntity.
"""

from __future__ import annotations

import logging

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PajGpsConfigEntry
from .coordinator import PajGpsCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PAJ GPS tracker entities from a config entry."""
    coordinator: PajGpsCoordinator = config_entry.runtime_data

    known_device_ids: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add entities for any device IDs not yet tracked."""
        current_ids = set(coordinator.data.devices.keys())
        new_ids = current_ids - known_device_ids
        if new_ids:
            sorted_new_ids = sorted(new_ids)
            async_add_entities(
                PajGPSDeviceTracker(coordinator, device_id)
                for device_id in sorted_new_ids
            )
            known_device_ids.update(sorted_new_ids)

    _async_add_new_devices()

    if not known_device_ids:
        _LOGGER.warning("No PAJ GPS devices found to add as trackers")

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class PajGPSDeviceTracker(CoordinatorEntity[PajGpsCoordinator], TrackerEntity):
    """Tracker entity that reads position from the coordinator snapshot."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:map-marker"

    def __init__(self, pajgps_coordinator: PajGpsCoordinator, device_id: int) -> None:
        """Initialize the GPS position tracker entity."""
        super().__init__(pajgps_coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{pajgps_coordinator.user_id}_{device_id}"

    @property
    def available(self) -> bool:
        """Return False when the device has been removed from the account."""
        return super().available and self._device_id in self.coordinator.data.devices

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this tracker."""
        return self.coordinator.get_device_info(self._device_id)

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the device."""
        tp = self.coordinator.data.positions.get(self._device_id)
        return float(tp.lat) if tp and tp.lat is not None else None

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        tp = self.coordinator.data.positions.get(self._device_id)
        return float(tp.lng) if tp and tp.lng is not None else None

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the tracker."""
        return SourceType.GPS
