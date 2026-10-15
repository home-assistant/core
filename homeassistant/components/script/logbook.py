"""Describe logbook events."""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_CONTEXT_ID,
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_ITEM_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LOGBOOK_ENTRY_RUN_ID,
    LazyEventPartialState,
)
from homeassistant.components.trace import ATTR_ITEM_ID, ATTR_RUN_ID
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback

from . import DOMAIN, EVENT_SCRIPT_STARTED


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None
    ],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event: LazyEventPartialState) -> dict[str, Any]:
        """Describe a logbook event."""
        data = event.data
        described: dict[str, Any] = {
            LOGBOOK_ENTRY_NAME: data.get(ATTR_NAME),
            LOGBOOK_ENTRY_MESSAGE: "started",
            LOGBOOK_ENTRY_ENTITY_ID: data.get(ATTR_ENTITY_ID),
            LOGBOOK_ENTRY_CONTEXT_ID: event.context_id,
        }
        if ATTR_ITEM_ID in data and ATTR_RUN_ID in data:
            described[LOGBOOK_ENTRY_ITEM_ID] = data[ATTR_ITEM_ID]
            described[LOGBOOK_ENTRY_RUN_ID] = data[ATTR_RUN_ID]
        return described

    async_describe_event(DOMAIN, EVENT_SCRIPT_STARTED, async_describe_logbook_event)
