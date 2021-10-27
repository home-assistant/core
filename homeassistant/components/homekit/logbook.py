"""Describe logbook events."""
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SERVICE
from homeassistant.core import callback

from .const import ATTR_DISPLAY_NAME, ATTR_VALUE, DOMAIN, EVENT_HOMEKIT_CHANGED


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        data = event.data
        entity_id = data.get(ATTR_ENTITY_ID)
        value = data.get(ATTR_VALUE)

        value_msg = f" to {value}" if value else ""
        message = f"send command {data[ATTR_SERVICE]}{value_msg} for {data[ATTR_DISPLAY_NAME]}"

        return {
            "name": "HomeKit",
            "message": message,
            "entity_id": entity_id,
        }

    async_describe_event(DOMAIN, EVENT_HOMEKIT_CHANGED, async_describe_logbook_event)
