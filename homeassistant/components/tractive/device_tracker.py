"""Support for Tractive device trackers."""

from typing import override

from aiotractive import Trackable

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TractiveConfigEntry, TractiveCoordinator
from .entity import TractiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tractive device trackers."""
    coordinator = entry.runtime_data

    async_add_entities(
        TractiveDeviceTracker(coordinator, trackable)
        for trackable in coordinator.trackables
    )


class TractiveDeviceTracker(TractiveEntity, TrackerEntity):
    """Tractive device tracker."""

    _attr_translation_key = "tracker"
    _attr_name = None

    def __init__(self, coordinator: TractiveCoordinator, trackable: Trackable) -> None:
        """Initialize tracker entity."""
        super().__init__(coordinator, trackable)
        self._attr_unique_id = trackable.pet_id

    @property
    @override
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._tracker_status.latitude

    @property
    @override
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._tracker_status.longitude

    @property
    @override
    def location_accuracy(self) -> float:
        """Return the location accuracy of the device."""
        return self._tracker_status.accuracy or 0

    @property
    @override
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        if self._tracker_status.sensor_used == "PHONE":
            return SourceType.BLUETOOTH
        return SourceType.GPS
