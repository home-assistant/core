"""Describe logbook events."""
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import callback

from . import ATTR_SOURCE, DOMAIN, EVENT_AUTOMATION_TRIGGERED


@callback
def async_describe_events(hass, async_describe_event):  # type: ignore
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):  # type: ignore
        """Describe a logbook event."""
        message = "has been triggered"
        if ATTR_SOURCE in event.data:
            message = f"{message} by {event.data[ATTR_SOURCE]}"
        return {
            "name": event.data.get(ATTR_NAME),
            "message": message,
            "source": event.data.get(ATTR_SOURCE),
            "entity_id": event.data.get(ATTR_ENTITY_ID),
        }

    async_describe_event(
        DOMAIN, EVENT_AUTOMATION_TRIGGERED, async_describe_logbook_event
    )
