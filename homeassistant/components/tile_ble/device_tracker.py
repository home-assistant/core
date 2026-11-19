"""Device tracker for the Tile BLE integration."""

from typing import override

from homeassistant.components.device_tracker import BaseScannerEntity, SourceType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TileBleConfigEntry, TileBleCoordinator
from .entity import TileBleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TileBleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tile BLE device tracker."""
    async_add_entities([TileBleDeviceTracker(entry.runtime_data, entry.title)])


class TileBleDeviceTracker(TileBleEntity, BaseScannerEntity):
    """Tracks whether a Tile is within Bluetooth range."""

    _attr_name = None
    _attr_source_type = SourceType.BLUETOOTH_LE

    def __init__(self, coordinator: TileBleCoordinator, name: str) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, name)
        self._attr_unique_id = coordinator.address

    @property
    @override
    def available(self) -> bool:
        """Return True, as a Tile out of range is away rather than unavailable."""
        return True

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if the Tile is within Bluetooth range."""
        return self.coordinator.available
