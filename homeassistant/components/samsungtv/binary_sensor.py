"""Support for SamsungTV binary sensors."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
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
        return

    if not coordinator.bridge.art_mode_support_unknown:
        return

    # Frame support is only known once device info was read, which fails
    # while the TV is unreachable, so add the sensor when it shows up later.
    remove_listener: CALLBACK_TYPE | None = None

    @callback
    def _async_add_when_supported() -> None:
        nonlocal remove_listener
        if remove_listener is None or coordinator.bridge.art_mode_support_unknown:
            return
        remove_listener()
        remove_listener = None
        if coordinator.bridge.supports_art_mode:
            async_add_entities([SamsungTVArtModeBinarySensor(coordinator=coordinator)])

    @callback
    def _async_remove_listener() -> None:
        if remove_listener is not None:
            remove_listener()

    remove_listener = coordinator.async_add_listener(_async_add_when_supported)
    entry.async_on_unload(_async_remove_listener)


class SamsungTVArtModeBinarySensor(SamsungTVEntity, BinarySensorEntity):
    """Binary sensor showing whether a Frame TV is in art mode."""

    _attr_translation_key = "art_mode"

    def __init__(self, *, coordinator: SamsungTVDataUpdateCoordinator) -> None:
        """Initialize the art mode binary sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{self._attr_unique_id}_art_mode"
        self._attr_is_on = coordinator.art_mode

    @property
    @override
    def available(self) -> bool:
        """Return True if the art mode is known, also while the TV is off."""
        return self.coordinator.last_update_success and not self._bridge.auth_failed

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._attr_is_on = self.coordinator.art_mode
        self.async_write_ha_state()
