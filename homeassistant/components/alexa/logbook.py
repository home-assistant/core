"""Describe logbook events."""
from homeassistant.core import callback

from .const import DOMAIN, EVENT_ALEXA_SMART_HOME


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        data = event.data
        entity_id = data["request"].get("entity_id")

        if entity_id:
            state = hass.states.get(entity_id)
            name = state.name if state else entity_id
            message = f"sent command {data['request']['namespace']}/{data['request']['name']} for {name}"
        else:
            message = (
                f"sent command {data['request']['namespace']}/{data['request']['name']}"
            )

        return {"name": "Amazon Alexa", "message": message, "entity_id": entity_id}

    async_describe_event(DOMAIN, EVENT_ALEXA_SMART_HOME, async_describe_logbook_event)
