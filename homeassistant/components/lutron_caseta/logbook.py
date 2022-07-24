"""Describe lutron_caseta logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ATTR_ACTION,
    ATTR_AREA_NAME,
    ATTR_DEVICE_NAME,
    ATTR_LEAP_BUTTON_NUMBER,
    ATTR_TYPE,
    DOMAIN,
    LUTRON_CASETA_BUTTON_EVENT,
)
from .device_trigger import LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_button_event(event: Event) -> dict[str, str]:
        """Describe lutron_caseta_button_event logbook event."""
        data = event.data
        device_type = data[ATTR_TYPE]
        leap_button_number = data[ATTR_LEAP_BUTTON_NUMBER]
        button_map = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP[device_type]
        button_description = button_map[leap_button_number]
        return {
            LOGBOOK_ENTRY_NAME: f"{data[ATTR_AREA_NAME]} {data[ATTR_DEVICE_NAME]}",
            LOGBOOK_ENTRY_MESSAGE: f"{data[ATTR_ACTION]} {button_description}",
        }

    async_describe_event(
        DOMAIN, LUTRON_CASETA_BUTTON_EVENT, async_describe_button_event
    )
