"""Describe logbook events."""
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
            "name": data.get(ATTR_NAME),
            "message": "started",
            "entity_id": data.get(ATTR_ENTITY_ID),
        }

    async_describe_event(DOMAIN, EVENT_SCRIPT_STARTED, async_describe_logbook_event)
