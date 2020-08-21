"""Describe logbook events."""
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import callback

from . import ATTR_TRIGGER, DOMAIN, EVENT_AUTOMATION_TRIGGERED


@callback
def async_describe_events(hass, async_describe_event):  # type: ignore
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):  # type: ignore
        """Describe a logbook event."""
        trigger = event.data.get(ATTR_TRIGGER)
        if not trigger:
            triggered_by = ""
        elif ATTR_ENTITY_ID in trigger:
            triggered_by = f" by {trigger[ATTR_ENTITY_ID]}"
        elif trigger["platform"] == "sun":
            triggered_by = f" by {trigger['event']}"
        elif trigger["platform"] == "event":
            triggered_by = f" by event: {trigger['event']['event_type']}"
        else:
            triggered_by = f" by {trigger['platform']} trigger"
        return {
            "name": event.data.get(ATTR_NAME),
            "message": f"has been triggered{triggered_by}",
            "entity_id": event.data.get(ATTR_ENTITY_ID),
        }

    async_describe_event(
        DOMAIN, EVENT_AUTOMATION_TRIGGERED, async_describe_logbook_event
    )
