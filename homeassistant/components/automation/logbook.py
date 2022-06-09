"""Describe logbook events."""
from homeassistant.components.logbook import LazyEventPartialState
from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_CONTEXT_ID,
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LOGBOOK_ENTRY_SOURCE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback

from . import ATTR_SOURCE, EVENT_AUTOMATION_TRIGGERED
from .const import DOMAIN


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event):  # type: ignore[no-untyped-def]
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event: LazyEventPartialState):  # type: ignore[no-untyped-def]
        """Describe a logbook event."""
        data = event.data
        message = "triggered"
        if ATTR_SOURCE in data:
            message = f"{message} by {data[ATTR_SOURCE]}"

        return {
            LOGBOOK_ENTRY_NAME: data.get(ATTR_NAME),
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_SOURCE: data.get(ATTR_SOURCE),
            LOGBOOK_ENTRY_ENTITY_ID: data.get(ATTR_ENTITY_ID),
            LOGBOOK_ENTRY_CONTEXT_ID: event.context_id,
        }

    async_describe_event(
        DOMAIN, EVENT_AUTOMATION_TRIGGERED, async_describe_logbook_event
    )
