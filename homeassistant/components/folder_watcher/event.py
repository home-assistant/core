"""Support for Folder watcher event entities."""

from __future__ import annotations

from functools import partial

from watchdog.events import (
    EVENT_TYPE_CLOSED,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
)

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

EVENT_DESCRIPTIONS = (
    EventEntityDescription(
        key=EVENT_TYPE_CLOSED,
        translation_key=EVENT_TYPE_CLOSED,
    ),
    EventEntityDescription(
        key=EVENT_TYPE_CREATED,
        translation_key=EVENT_TYPE_CREATED,
    ),
    EventEntityDescription(
        key=EVENT_TYPE_DELETED,
        translation_key=EVENT_TYPE_DELETED,
    ),
    EventEntityDescription(
        key=EVENT_TYPE_MODIFIED,
        translation_key=EVENT_TYPE_MODIFIED,
    ),
    EventEntityDescription(
        key=EVENT_TYPE_MOVED,
        translation_key=EVENT_TYPE_MOVED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Folder Watcher event."""

    async_add_entities(
        FolderWatcherEventEntity(description, entry)
        for description in EVENT_DESCRIPTIONS
    )


class FolderWatcherEventEntity(EventEntity):
    """Representation of a Xiaomi event entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_event_types = [
        EVENT_TYPE_CLOSED,
        EVENT_TYPE_CREATED,
        EVENT_TYPE_DELETED,
        EVENT_TYPE_MODIFIED,
        EVENT_TYPE_MOVED,
    ]

    def __init__(
        self,
        description: EventEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialise a Xiaomi event entity."""
        self.entity_description = description
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Folder Watcher",
        )
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"
        self._entry = entry

    @callback
    def _async_handle_event(self, event: str) -> None:
        """Handle the event."""
        # Fix add additional attributes as with the bus event firing
        self._trigger_event(event)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        signal = f"folder_watcher-{self._entry.entry_id}-{self.entity_description.key}"
        _handle = partial(self._async_handle_event, self.entity_description.key)
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, _handle))
