"""Support for Folder watcher event entities."""

from __future__ import annotations

from typing import Any

from watchdog.events import (
    EVENT_TYPE_CLOSED,
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
)

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Folder Watcher event."""

    async_add_entities([FolderWatcherEventEntity(entry)])


class FolderWatcherEventEntity(EventEntity):
    """Representation of a Folder watcher event entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_event_types = [
        EVENT_TYPE_CLOSED,
        EVENT_TYPE_CREATED,
        EVENT_TYPE_DELETED,
        EVENT_TYPE_MODIFIED,
        EVENT_TYPE_MOVED,
    ]
    _attr_name = None
    _attr_translation_key = DOMAIN

    def __init__(
        self,
        entry: ConfigEntry,
    ) -> None:
        """Initialise a Folder watcher event entity."""
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Folder watcher",
        )
        self._attr_unique_id = entry.entry_id
        self._entry = entry

    @callback
    def _async_handle_event(self, event: str, _extra: dict[str, Any]) -> None:
        """Handle the event."""
        self._trigger_event(event, _extra)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        signal = f"folder_watcher-{self._entry.entry_id}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self._async_handle_event)
        )
