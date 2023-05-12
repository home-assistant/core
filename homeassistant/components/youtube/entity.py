"""Entity representing a YouTube account."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .api import AsyncConfigEntryAuth
from .const import DOMAIN, MANUFACTURER


class YouTubeChannelEntity(Entity):
    """An HA implementation for YouTube entity."""

    def __init__(
        self,
        auth: AsyncConfigEntryAuth,
        description: EntityDescription,
        channel_name: str,
    ) -> None:
        """Initialize a Google Mail entity."""
        self.auth = auth
        self.entity_description = description
        self._attr_unique_id = f"{auth.oauth_session.config_entry.entry_id}_{channel_name}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, auth.oauth_session.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=channel_name,
        )
