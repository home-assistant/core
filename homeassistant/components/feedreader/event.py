"""Event entities for RSS/Atom feeds."""

from __future__ import annotations

from collections.abc import Mapping
import logging

from homeassistant.components.event import EventEntity
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FeedReaderConfigEntry
from .const import DOMAIN, EVENT_FEEDREADER
from .coordinator import FeedReaderCoordinator

LOGGER = logging.getLogger(__name__)

ATTR_CONTENT = "content"
ATTR_LINK = "link"
ATTR_TITLE = "title"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FeedReaderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EZVIZ cameras based on a config entry."""
    coordinator: FeedReaderCoordinator = entry.runtime_data

    async_add_entities([FeedReaderEvent(coordinator)])


class FeedReaderEvent(CoordinatorEntity[FeedReaderCoordinator], EventEntity):
    """Representation of a feedreader event."""

    _attr_event_types = [EVENT_FEEDREADER]
    _attr_name = None
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({ATTR_CONTENT, ATTR_TITLE, ATTR_LINK})
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

        @callback
        def _filter(event: Mapping) -> bool:
            return event.get("feed_url") == self.coordinator.url

        self.hass.bus.async_listen(EVENT_FEEDREADER, self._async_handle_event, _filter)

    @callback
    def _async_handle_event(self, event: Event) -> None:
        self._trigger_event(
            str(event.event_type),
            {
                ATTR_TITLE: event.data["title"],
                ATTR_LINK: event.data["link"],
                ATTR_CONTENT: event.data["content"],
            },
        )
        self.async_write_ha_state()
