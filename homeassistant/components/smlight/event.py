"""Event platform for SMLIGHT."""

from __future__ import annotations

import logging

from pysmlight.const import Events as SmEvents
from pysmlight.sse import MessageEvent

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads_object

from .coordinator import SmConfigEntry, SmDataUpdateCoordinator
from .entity import SmEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

EVENT_TYPE_IR_CODE = "ir_code_received"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize event platform for SMLIGHT device."""
    coordinator = entry.runtime_data.data

    if coordinator.data.info.has_peripherals:
        async_add_entities([SmEventEntity(coordinator, [EVENT_TYPE_IR_CODE])])


class SmEventEntity(SmEntity, EventEntity):
    """Representation of a generic SLZB Event entity."""

    _attr_translation_key = "event"
    _attr_should_poll = False

    def __init__(
        self, coordinator: SmDataUpdateCoordinator, event_types: list[str]
    ) -> None:
        """Initialize the SLZB Event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}_event"
        self._attr_event_types = event_types

    async def async_added_to_hass(self) -> None:
        """Register callbacks when added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.coordinator.client.sse.register_callback(
                SmEvents.IR_CODE, self._handle_ir_event
            )
        )

    @callback
    def _handle_ir_event(self, event: MessageEvent) -> None:
        """Handle incoming SSE IR events."""
        try:
            data = json_loads_object(event.data)
        except ValueError:
            _LOGGER.debug("Received invalid IR event data: %s", event.data)
            return
        self._trigger_event(EVENT_TYPE_IR_CODE, data)
        self.async_write_ha_state()
