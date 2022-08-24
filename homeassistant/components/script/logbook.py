"""Describe logbook events."""
from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_CONTEXT_ID,
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import callback

from . import DOMAIN, EVENT_SCRIPT_STARTED


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):
        """Describe the logbook event."""
        data = event.data
        return {
            LOGBOOK_ENTRY_NAME: data.get(ATTR_NAME),
            LOGBOOK_ENTRY_MESSAGE: "started",
            LOGBOOK_ENTRY_ENTITY_ID: data.get(ATTR_ENTITY_ID),
            LOGBOOK_ENTRY_CONTEXT_ID: event.context_id,
        }

    async_describe_event(DOMAIN, EVENT_SCRIPT_STARTED, async_describe_logbook_event)
