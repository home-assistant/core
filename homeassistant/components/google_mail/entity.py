"""Entity representing a Google Mail account."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN, MANUFACTURER


class GoogleMailEntity(Entity):
    """An HA implementation for Google Mail entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, description: EntityDescription) -> None:
        """Initialize a Google Mail entity."""
        self.data: dict[str, Any] = {}
        self.entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=entry.unique_id,
        )
