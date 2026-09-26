"""Common entity for Fujitsu IR integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class FujitsuIrEntity(Entity):
    """Fujitsu IR base entity providing common device info."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize Fujitsu IR entity."""
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Fujitsu AC",
            manufacturer="Fujitsu General",
        )
