"""Describe hue logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.const import CONF_DEVICE_ID, CONF_EVENT, CONF_ID, CONF_TYPE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import ATTR_HUE_EVENT, CONF_SUBTYPE, DOMAIN

TRIGGER_SUBTYPE = {
    "button_1": "First button",
    "button_2": "Second button",
    "button_3": "Third button",
    "button_4": "Fourth button",
    "double_buttons_1_3": "First and Third buttons",
    "double_buttons_2_4": "Second and Fourth buttons",
    "dim_down": "Dim down",
    "dim_up": "Dim up",
    "turn_off": "Turn off",
    "turn_on": "Turn on",
    "1": "First button",
    "2": "Second button",
    "3": "Third button",
    "4": "Fourth button",
}
TRIGGER_TYPE = {
    "remote_button_long_release": '"{subtype}" button released after long press',
    "remote_button_short_press": '"{subtype}" button pressed',
    "remote_button_short_release": '"{subtype}" button released',
    "remote_double_button_long_press": 'Both "{subtype}" released after long press',
    "remote_double_button_short_press": 'Both "{subtype}" released',
    "initial_press": 'Button "{subtype}" pressed initially',
    "repeat": 'Button "{subtype}" held down',
    "short_release": 'Button "{subtype}" released after short press',
    "long_release": 'Button "{subtype}" released after long press',
    "double_short_release": 'Both "{subtype}" released',
}

UNKNOWN_TYPE = "Unknown Type"
UNKNOWN_SUB_TYPE = "Unknown Sub Type"


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe hue logbook events."""

    @callback
    def async_describe_hue_event(event: Event) -> dict[str, str]:
        """Describe hue logbook event."""
        data = event.data
        name: str | None = None
        if dev_ent := dr.async_get(hass).async_get(data[CONF_DEVICE_ID]):
            name = dev_ent.name
        if name is None:
            name = data[CONF_ID]
        if CONF_TYPE in data:  # v2
            subtype = TRIGGER_SUBTYPE.get(str(data[CONF_SUBTYPE]), UNKNOWN_SUB_TYPE)
            message = TRIGGER_TYPE.get(data[CONF_TYPE], UNKNOWN_TYPE).format(
                subtype=subtype
            )
        else:
            message = f"Event {data[CONF_EVENT]}"  # v1
        return {
            "name": name,
            "message": str(message),
        }

    async_describe_event(DOMAIN, ATTR_HUE_EVENT, async_describe_hue_event)
