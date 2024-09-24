"""Describe logbook events."""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_ALEXA_SMART_HOME


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event: Event) -> dict[str, Any]:
        """Describe a logbook event."""
        data = event.data

        if entity_id := data["request"].get("entity_id"):
            state = hass.states.get(entity_id)
            name = state.name if state else entity_id
            message = (
                "sent command"
                f" {data['request']['namespace']}/{data['request']['name']} for {name}"
            )
        else:
            message = (
                f"sent command {data['request']['namespace']}/{data['request']['name']}"
            )

        return {
            LOGBOOK_ENTRY_NAME: "Amazon Alexa",
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_ENTITY_ID: entity_id,
        }

    async_describe_event(DOMAIN, EVENT_ALEXA_SMART_HOME, async_describe_logbook_event)
