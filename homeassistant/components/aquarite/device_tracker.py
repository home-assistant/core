"""Aquarite Device Tracker entity."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pool location tracker."""
    coordinator = entry.runtime_data.coordinator
    pool_id = coordinator.pool_id
    pool_name = entry.title

    async_add_entities([
        PoolLocationDeviceTracker(coordinator, pool_id, pool_name)
    ])


class PoolLocationDeviceTracker(AquariteEntity, TrackerEntity):
    """Device tracker representing pool location."""

    _attr_source_type = SourceType.GPS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "location"

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, pool_id, pool_name)
        self._attr_unique_id = self.build_unique_id("location-tracker")

    @property
    def latitude(self) -> float | None:
        """Return latitude directly from coordinator data."""
        try:
            val = self.coordinator.get_value("form.lat")
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def longitude(self) -> float | None:
        """Return longitude directly from coordinator data."""
        try:
            val = self.coordinator.get_value("form.lng")
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None
