"""Describe elkm1 logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ATTR_KEY,
    ATTR_KEY_NAME,
    ATTR_KEYPAD_ID,
    ATTR_KEYPAD_NAME,
    DOMAIN,
    EVENT_ELKM1_KEYPAD_KEY_PRESSED,
)


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_button_event(event: Event) -> dict[str, str]:
        """Describe elkm1 logbook event."""
        data = event.data
        keypad_name = data.get(
            ATTR_KEYPAD_NAME, data[ATTR_KEYPAD_ID]
        )  # added in 2022.6
        return {
            LOGBOOK_ENTRY_NAME: f"Elk Keypad {keypad_name}",
            LOGBOOK_ENTRY_MESSAGE: f"pressed {data[ATTR_KEY_NAME]} ({data[ATTR_KEY]})",
        }

    async_describe_event(
        DOMAIN, EVENT_ELKM1_KEYPAD_KEY_PRESSED, async_describe_button_event
    )
