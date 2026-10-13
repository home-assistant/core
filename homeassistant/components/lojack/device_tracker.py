"""Device tracker platform for LoJack integration."""

from typing import override

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LoJackConfigEntry
from .entity import LoJackEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LoJack device tracker from a config entry."""
    async_add_entities(
        LoJackDeviceTracker(coordinator)
        for coordinator in entry.runtime_data.coordinators
    )


class LoJackDeviceTracker(LoJackEntity, TrackerEntity):
    """Representation of a LoJack device tracker."""

    _attr_name = None  # Main entity of the device, uses device name directly

    @property
    @override
    def latitude(self) -> float | None:
        """Return the latitude of the device."""
        return self.coordinator.data.latitude

    @property
    @override
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        return self.coordinator.data.longitude

    @property
    @override
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if self.coordinator.data.accuracy is not None:
            return int(self.coordinator.data.accuracy)
        return 0
