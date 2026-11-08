"""Binary sensors for Samsung TVs."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bridge import SamsungTVWSBridge
from .coordinator import SamsungTVConfigEntry, SamsungTVDataUpdateCoordinator
from .entity import SamsungTVEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SamsungTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Art Mode status when the TV reports support."""
    coordinator = entry.runtime_data
    if not isinstance(bridge := coordinator.bridge, SamsungTVWSBridge):
        return
    added = False

    @callback
    def async_add_art_mode_sensor() -> None:
        nonlocal added
        if added or not bridge.supports_art_mode:
            return
        added = True
        async_add_entities([SamsungTVArtModeSensor(coordinator)])

    entry.async_on_unload(coordinator.async_add_listener(async_add_art_mode_sensor))
    async_add_art_mode_sensor()


class SamsungTVArtModeSensor(SamsungTVEntity, BinarySensorEntity):
    """Represent whether Art Mode is active."""

    _attr_translation_key = "art_mode"

    def __init__(self, coordinator: SamsungTVDataUpdateCoordinator) -> None:
        """Initialize the Art Mode sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{self.unique_id}_art_mode"

    @property
    @override
    def available(self) -> bool:
        """Return whether Art Mode status is available."""
        return super().available and self.coordinator.art_mode is not None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether Art Mode is active."""
        return self.coordinator.art_mode
