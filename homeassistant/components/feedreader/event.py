"""Event entities for RSS/Atom feeds."""

from __future__ import annotations

import html
import logging

from feedparser import FeedParserDict

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FeedReaderConfigEntry
from .const import DOMAIN, EVENT_FEEDREADER
from .coordinator import FeedReaderCoordinator

LOGGER = logging.getLogger(__name__)

ATTR_CONTENT = "content"
ATTR_DESCRIPTION = "description"
ATTR_LINK = "link"
ATTR_TITLE = "title"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FeedReaderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event entities for feedreader."""
    coordinator = entry.runtime_data

    async_add_entities([FeedReaderEvent(coordinator)])


class FeedReaderEvent(CoordinatorEntity[FeedReaderCoordinator], EventEntity):
    """Representation of a feedreader event."""

    _attr_event_types = [EVENT_FEEDREADER]
    _attr_name = None
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset(
        {ATTR_CONTENT, ATTR_DESCRIPTION, ATTR_TITLE, ATTR_LINK}
    )
    coordinator: FeedReaderCoordinator

    def __init__(self, coordinator: FeedReaderCoordinator) -> None:
        """Initialize the feedreader event."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_latest_feed"
        self._attr_translation_key = "latest_feed"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            configuration_url=coordinator.url,
            manufacturer=coordinator.feed_author,
            sw_version=coordinator.feed_version,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_handle_update)
        )

    @callback
    def _async_handle_update(self) -> None:
        if (data := self.coordinator.data) is None or not data:
            return

        # RSS feeds are normally sorted reverse chronologically by published date
        # so we always take the first entry in list, since we only care about the latest entry
        feed_data: FeedParserDict = data[0]

        if description := feed_data.get("description"):
            description = html.unescape(description)

        if title := feed_data.get("title"):
            title = html.unescape(title)

        if content := feed_data.get("content"):
            if isinstance(content, list) and isinstance(content[0], dict):
                content = content[0].get("value")
            content = html.unescape(content)

        self._trigger_event(
            EVENT_FEEDREADER,
            {
                ATTR_DESCRIPTION: description,
                ATTR_TITLE: title,
                ATTR_LINK: feed_data.get("link"),
                ATTR_CONTENT: content,
            },
        )
        self.async_write_ha_state()
