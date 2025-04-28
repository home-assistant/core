"""Support for setting the Deluge BitTorrent client in Pause."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DelugeConfigEntry, DelugeDataUpdateCoordinator
from .entity import DelugeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DelugeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Deluge switch."""
    async_add_entities([DelugeSwitch(entry.runtime_data)])


class DelugeSwitch(DelugeEntity, SwitchEntity):
    """Representation of a Deluge switch."""

    _attr_name = None

    def __init__(self, coordinator: DelugeDataUpdateCoordinator) -> None:
        """Initialize the Deluge switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_enabled"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        torrent_ids = self.coordinator.api.call("core.get_session_state")
        self.coordinator.api.call("core.resume_torrent", torrent_ids)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        torrent_ids = self.coordinator.api.call("core.get_session_state")
        self.coordinator.api.call("core.pause_torrent", torrent_ids)

    @property
    def is_on(self) -> bool:
        """Return state of the switch."""
        if self.coordinator.data:
            data = self.coordinator.data[Platform.SWITCH]
            for torrent in data.values():
                item = torrent.popitem()
                if not item[1]:
                    return True
        return False
