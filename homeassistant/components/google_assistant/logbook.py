"""Describe logbook events."""

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import callback

from .const import DOMAIN, EVENT_COMMAND_RECEIVED, SOURCE_CLOUD

COMMON_COMMAND_PREFIX = "action.devices.commands."


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        commands = []

        for command_payload in event.data["execution"]:
            command = command_payload["command"].removeprefix(COMMON_COMMAND_PREFIX)
            commands.append(command)

        message = f"sent command {', '.join(commands)}"
        if event.data["source"] != SOURCE_CLOUD:
            message += f" (via {event.data['source']})"

        return {LOGBOOK_ENTRY_NAME: "Google Assistant", LOGBOOK_ENTRY_MESSAGE: message}

    async_describe_event(DOMAIN, EVENT_COMMAND_RECEIVED, async_describe_logbook_event)
