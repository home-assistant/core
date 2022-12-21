"""Describe logbook events."""
from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SERVICE
from homeassistant.core import Event, HomeAssistant, callback

from .const import ATTR_DISPLAY_NAME, ATTR_VALUE, DOMAIN, EVENT_HOMEKIT_CHANGED


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event: Event) -> dict[str, Any]:
        """Describe a logbook event."""
        data = event.data
        entity_id = data.get(ATTR_ENTITY_ID)
        value = data.get(ATTR_VALUE)

        value_msg = f" to {value}" if value else ""
        message = f"send command {data[ATTR_SERVICE]}{value_msg} for {data[ATTR_DISPLAY_NAME]}"

        return {
            LOGBOOK_ENTRY_NAME: "HomeKit",
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_ENTITY_ID: entity_id,
        }

    async_describe_event(DOMAIN, EVENT_HOMEKIT_CHANGED, async_describe_logbook_event)
