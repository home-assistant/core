"""Base entity for Google Weather."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import GoogleWeatherConfigEntry


class GoogleWeatherBaseEntity(Entity):
    """Base entity for all Google Weather entities."""

    _attr_has_entity_name = True

    def __init__(
        self, config_entry: GoogleWeatherConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize base entity."""
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Google",
            entry_type=DeviceEntryType.SERVICE,
        )
