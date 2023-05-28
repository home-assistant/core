"""Entity representing a YouTube account."""
from __future__ import annotations

from typing import Any

from homeassistant.const import ATTR_ID
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_TITLE, DOMAIN, MANUFACTURER
from .coordinator import YouTubeDataUpdateCoordinator


class YouTubeChannelEntity(CoordinatorEntity):
    """An HA implementation for YouTube entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YouTubeDataUpdateCoordinator,
        description: EntityDescription,
        channel: dict[str, Any],
    ) -> None:
        """Initialize a Google Mail entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{channel[ATTR_ID]}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{channel[ATTR_ID]}")
            },
            manufacturer=MANUFACTURER,
            name=channel[ATTR_TITLE],
        )
        self._channel = channel
