"""Common entity for the Novy Cooker Hood integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class NovyCookerHoodEntity(Entity):
    """Novy Cooker Hood base entity."""

    _attr_assumed_state = True
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Novy",
            model="Cooker Hood",
        )
