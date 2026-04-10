"""The slack integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DEFAULT_NAME, DOMAIN

if TYPE_CHECKING:
    from . import SlackConfigEntry, SlackData


class SlackEntity(Entity):
    """Representation of a Slack entity."""

    def __init__(
        self,
        data: SlackData,
        description: EntityDescription,
        entry: SlackConfigEntry,
    ) -> None:
        """Initialize a Slack entity."""
        self._client = data.client
        self.entity_description = description
        self._attr_unique_id = f"{data.user_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=data.url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=entry.title,
        )
