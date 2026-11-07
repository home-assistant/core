"""Base entity for SilverCrest Infrared integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_DEVICE_TYPE, DEVICE_NAMES, DOMAIN


class SilverCrestIrBaseEntity(Entity):
    """Base entity for SilverCrest Infrared."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="SilverCrest",
            translation_key=entry.data[CONF_DEVICE_TYPE],
            model=DEVICE_NAMES[entry.data[CONF_DEVICE_TYPE]],
        )
        self._entry = entry
