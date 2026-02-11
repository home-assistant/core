"""The slack integration."""

from __future__ import annotations

from slack_sdk.web.async_client import AsyncWebClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import ATTR_URL, ATTR_USER_ID, DATA_CLIENT, DEFAULT_NAME, DOMAIN


class SlackEntity(Entity):
    """Representation of a Slack entity."""

    def __init__(
        self,
        data: dict[str, AsyncWebClient],
        description: EntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a Slack entity."""
        self._client: AsyncWebClient = data[DATA_CLIENT]
        self.entity_description = description
        self._attr_unique_id = f"{data[ATTR_USER_ID]}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=str(data[ATTR_URL]),
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=entry.title,
        )
