"""Device tracker platform for fressnapf_tracker."""

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FressnapfTrackerConfigEntry, FressnapfTrackerDataUpdateCoordinator
from .entity import FressnapfTrackerBaseEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FressnapfTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fressnapf_tracker device_trackers."""
    async_add_entities(
        FressnapfTrackerDeviceTracker(coordinator) for coordinator in entry.runtime_data
    )


class FressnapfTrackerDeviceTracker(FressnapfTrackerBaseEntity, TrackerEntity):
    """fressnapf_tracker device tracker."""

    _attr_name = None
    _attr_translation_key = "pet"

    def __init__(
        self,
        coordinator: FressnapfTrackerDataUpdateCoordinator,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device.serialnumber

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.position is not None

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture url."""
        return self.coordinator.data.icon

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if self.coordinator.data.position is not None:
            return self.coordinator.data.position.lat
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if self.coordinator.data.position is not None:
            return self.coordinator.data.position.lng
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> float:
        """Return the location accuracy of the device.

        Value in meters.
        """
        if self.coordinator.data.position is not None:
            return float(self.coordinator.data.position.accuracy)
        return 0
