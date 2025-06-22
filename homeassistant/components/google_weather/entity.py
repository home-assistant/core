"""Base entity for Google Weather."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import GoogleWeatherConfigEntry


class GoogleWeatherBaseEntity(Entity):
    """Base entity for all Google Weather entities."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: GoogleWeatherConfigEntry) -> None:
        """Initialize base entity."""
        assert config_entry.unique_id
        self._attr_unique_id = config_entry.unique_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.unique_id)},
            manufacturer="Google",
        )
