"""Entity representing a YouTube account."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN, MANUFACTURER


class YouTubeChannelEntity(Entity):
    """An HA implementation for YouTube entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        description: EntityDescription,
        channel_name: str,
        channel_id: str,
    ) -> None:
        """Initialize a Google Mail entity."""
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{channel_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry.entry_id}_{channel_id}")},
            manufacturer=MANUFACTURER,
            name=channel_name,
        )
