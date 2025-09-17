"""Base entity for the Fish Audio integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class FishAudioEntity(Entity):
    """Base class for Fish Audio entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__()
        self._session = entry.runtime_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Fish Audio",
            entry_type=DeviceEntryType.SERVICE,
        )
        self.entry = entry
