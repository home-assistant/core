"""Describe logbook events."""
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback

from .const import DOMAIN, EVENT_COMMAND_RECEIVED

COMMON_COMMAND_PREFIX = "action.devices.commands."


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        entity_id = event.data[ATTR_ENTITY_ID]
        state = hass.states.get(entity_id)
        name = state.name if state else entity_id

        command = event.data["execution"]["command"]
        if command.startswith(COMMON_COMMAND_PREFIX):
            command = command[len(COMMON_COMMAND_PREFIX) :]

        message = f"sent command {command} for {name} (via {event.data['source']})"

        return {"name": "Google Assistant", "message": message, "entity_id": entity_id}

    async_describe_event(DOMAIN, EVENT_COMMAND_RECEIVED, async_describe_logbook_event)
