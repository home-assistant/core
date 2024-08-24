"""Support for SLZB-06 events."""

from __future__ import annotations

import json

from pysmlight.const import Events as SmEvents, RebootReasons
from pysmlight.sse import MessageEvent

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmConfigEntry
from .coordinator import SmDataUpdateCoordinator
from .entity import SmEntity

EVENT_TYPE_CORE_REBOOT = "core-reboot"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the slzb event platform."""
    coordinator = entry.runtime_data.data
    async_add_entities([SmEvent(coordinator)])


class SmEvent(SmEntity, EventEntity):
    """Representation of a slzb event entity."""

    _attr_event_types = [EVENT_TYPE_CORE_REBOOT]

    _attr_should_poll = False
    _attr_translation_key = "event"

    def __init__(self, coordinator: SmDataUpdateCoordinator) -> None:
        """Initialize the slzb event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_translation_key}"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.client.sse.register_callback(
                SmEvents.REBOOT, self._async_handle_event
            )
        )

    @callback
    def _async_handle_event(self, event: MessageEvent) -> None:
        """Handle the reboot event."""
        data = json.loads(event.data)
        data["reason"] = RebootReasons(data["reason"]).name

        self._trigger_event(EVENT_TYPE_CORE_REBOOT, data)
        self.async_write_ha_state()
