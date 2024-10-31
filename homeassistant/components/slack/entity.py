"""The slack integration."""

from __future__ import annotations

from slack import WebClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import ATTR_URL, ATTR_USER_ID, DATA_CLIENT, DEFAULT_NAME, DOMAIN


class SlackEntity(Entity):
    """Representation of a Slack entity."""

    _attr_attribution = "Data provided by Slack"
    _attr_has_entity_name = True

    def __init__(
        self,
        data: dict[str, str | WebClient],
        description: EntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a Slack entity."""
        self._client = data[DATA_CLIENT]
        self.entity_description = description
        self._attr_unique_id = f"{data[ATTR_USER_ID]}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=data[ATTR_URL],
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=entry.title,
        )
