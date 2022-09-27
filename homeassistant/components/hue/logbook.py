"""Describe hue logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import CONF_DEVICE_ID, CONF_EVENT, CONF_ID, CONF_TYPE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import ATTR_HUE_EVENT, CONF_SUBTYPE, DOMAIN

TRIGGER_SUBTYPE = {
    "button_1": "first button",
    "button_2": "second button",
    "button_3": "third button",
    "button_4": "fourth button",
    "double_buttons_1_3": "first and third buttons",
    "double_buttons_2_4": "second and fourth buttons",
    "dim_down": "dim down",
    "dim_up": "dim up",
    "turn_off": "turn off",
    "turn_on": "turn on",
    "1": "first button",
    "2": "second button",
    "3": "third button",
    "4": "fourth button",
    "clock_wise": "Rotation clockwise",
    "counter_clock_wise": "Rotation counter-clockwise",
}
TRIGGER_TYPE = {
    "remote_button_long_release": "{subtype} released after long press",
    "remote_button_short_press": "{subtype} pressed",
    "remote_button_short_release": "{subtype} released",
    "remote_double_button_long_press": "both {subtype} released after long press",
    "remote_double_button_short_press": "both {subtype} released",
    "initial_press": "{subtype} pressed initially",
    "repeat": "{subtype} held down",
    "short_release": "{subtype} released after short press",
    "long_release": "{subtype} released after long press",
    "double_short_release": "both {subtype} released",
    "start": '"{subtype}" pressed initially',
}

UNKNOWN_TYPE = "unknown type"
UNKNOWN_SUB_TYPE = "unknown sub type"


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
            LOGBOOK_ENTRY_NAME: name,
            LOGBOOK_ENTRY_MESSAGE: message,
        }

    async_describe_event(DOMAIN, ATTR_HUE_EVENT, async_describe_hue_event)
