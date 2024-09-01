"""Base entity for the Twente Milieu integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TwenteMilieuDataUpdateCoordinator
from .const import DOMAIN


class TwenteMilieuEntity(CoordinatorEntity[TwenteMilieuDataUpdateCoordinator], Entity):
    """Defines a Twente Milieu entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the Twente Milieu entity."""
        super().__init__(coordinator=entry.runtime_data)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.twentemilieu.nl",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(entry.data[CONF_ID]))},
            manufacturer="Twente Milieu",
            name="Twente Milieu",
        )
