"""Support for SamsungTV binary sensors."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SamsungTVConfigEntry, SamsungTVDataUpdateCoordinator
from .entity import SamsungTVEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SamsungTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SamsungTV binary sensors from a config entry."""
    coordinator = entry.runtime_data
    if coordinator.bridge.supports_art_mode:
        async_add_entities([SamsungTVArtModeBinarySensor(coordinator=coordinator)])


class SamsungTVArtModeBinarySensor(SamsungTVEntity, BinarySensorEntity):
    """Binary sensor showing whether a Frame TV is in art mode."""

    _attr_translation_key = "art_mode"

    def __init__(self, *, coordinator: SamsungTVDataUpdateCoordinator) -> None:
        """Initialize the art mode binary sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{self._attr_unique_id}_art_mode"
        self._attr_is_on = coordinator.art_mode

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._attr_is_on = self.coordinator.art_mode
        self.async_write_ha_state()
