"""Describe deCONZ logbook events."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import ATTR_DEVICE_ID, CONF_EVENT, CONF_ID
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.device_registry as dr

from .const import CONF_GESTURE, DOMAIN as DECONZ_DOMAIN
from .deconz_event import CONF_DECONZ_ALARM_EVENT, CONF_DECONZ_EVENT
from .device_trigger import (
    CONF_BOTH_BUTTONS,
    CONF_BOTTOM_BUTTONS,
    CONF_BUTTON_1,
    CONF_BUTTON_2,
    CONF_BUTTON_3,
    CONF_BUTTON_4,
    CONF_BUTTON_5,
    CONF_BUTTON_6,
    CONF_BUTTON_7,
    CONF_BUTTON_8,
    CONF_CLOSE,
    CONF_DIM_DOWN,
    CONF_DIM_UP,
    CONF_DOUBLE_PRESS,
    CONF_DOUBLE_TAP,
    CONF_LEFT,
    CONF_LONG_PRESS,
    CONF_LONG_RELEASE,
    CONF_MOVE,
    CONF_OPEN,
    CONF_QUADRUPLE_PRESS,
    CONF_QUINTUPLE_PRESS,
    CONF_RIGHT,
    CONF_ROTATE_FROM_SIDE_1,
    CONF_ROTATE_FROM_SIDE_2,
    CONF_ROTATE_FROM_SIDE_3,
    CONF_ROTATE_FROM_SIDE_4,
    CONF_ROTATE_FROM_SIDE_5,
    CONF_ROTATE_FROM_SIDE_6,
    CONF_ROTATED,
    CONF_ROTATED_FAST,
    CONF_ROTATION_STOPPED,
    CONF_SHAKE,
    CONF_SHORT_PRESS,
    CONF_SHORT_RELEASE,
    CONF_SIDE_1,
    CONF_SIDE_2,
    CONF_SIDE_3,
    CONF_SIDE_4,
    CONF_SIDE_5,
    CONF_SIDE_6,
    CONF_TOP_BUTTONS,
    CONF_TRIPLE_PRESS,
    CONF_TURN_OFF,
    CONF_TURN_ON,
    REMOTES,
    _get_deconz_event_from_device,
)

ACTIONS = {
    CONF_SHORT_PRESS: "Short press",
    CONF_SHORT_RELEASE: "Short release",
    CONF_LONG_PRESS: "Long press",
    CONF_LONG_RELEASE: "Long release",
    CONF_DOUBLE_PRESS: "Double press",
    CONF_TRIPLE_PRESS: "Triple press",
    CONF_QUADRUPLE_PRESS: "Quadruple press",
    CONF_QUINTUPLE_PRESS: "Quintuple press",
    CONF_ROTATED: "Rotated",
    CONF_ROTATED_FAST: "Rotated fast",
    CONF_ROTATION_STOPPED: "Rotated stopped",
    CONF_MOVE: "Move",
    CONF_DOUBLE_TAP: "Double tap",
    CONF_SHAKE: "Shake",
    CONF_ROTATE_FROM_SIDE_1: "Rotate from side 1",
    CONF_ROTATE_FROM_SIDE_2: "Rotate from side 2",
    CONF_ROTATE_FROM_SIDE_3: "Rotate from side 3",
    CONF_ROTATE_FROM_SIDE_4: "Rotate from side 4",
    CONF_ROTATE_FROM_SIDE_5: "Rotate from side 5",
    CONF_ROTATE_FROM_SIDE_6: "Rotate from side 6",
}

INTERFACES = {
    CONF_TURN_ON: "Turn on",
    CONF_TURN_OFF: "Turn off",
    CONF_DIM_UP: "Dim up",
    CONF_DIM_DOWN: "Dim down",
    CONF_LEFT: "Left",
    CONF_RIGHT: "Right",
    CONF_OPEN: "Open",
    CONF_CLOSE: "Close",
    CONF_BOTH_BUTTONS: "Both buttons",
    CONF_TOP_BUTTONS: "Top buttons",
    CONF_BOTTOM_BUTTONS: "Bottom buttons",
    CONF_BUTTON_1: "Button 1",
    CONF_BUTTON_2: "Button 2",
    CONF_BUTTON_3: "Button 3",
    CONF_BUTTON_4: "Button 4",
    CONF_BUTTON_5: "Button 5",
    CONF_BUTTON_6: "Button 6",
    CONF_BUTTON_7: "Button 7",
    CONF_BUTTON_8: "Button 8",
    CONF_SIDE_1: "Side 1",
    CONF_SIDE_2: "Side 2",
    CONF_SIDE_3: "Side 3",
    CONF_SIDE_4: "Side 4",
    CONF_SIDE_5: "Side 5",
    CONF_SIDE_6: "Side 6",
}


def _get_device_event_description(
    modelid: str, event: int
) -> tuple[str | None, str | None]:
    """Get device event description."""
    device_event_descriptions = REMOTES[modelid]

    for event_type_tuple, event_dict in device_event_descriptions.items():
        if event == event_dict.get(CONF_EVENT):
            return event_type_tuple
        if event == event_dict.get(CONF_GESTURE):
            return event_type_tuple

    return (None, None)


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""
    device_registry = dr.async_get(hass)

    @callback
    def async_describe_deconz_alarm_event(event: Event) -> dict[str, str]:
        """Describe deCONZ logbook alarm event."""
        if device := device_registry.devices.get(event.data[ATTR_DEVICE_ID]):
            deconz_alarm_event = _get_deconz_event_from_device(hass, device)
            name = deconz_alarm_event.device.name
        else:
            name = event.data[CONF_ID]

        data = event.data[CONF_EVENT]

        return {
            LOGBOOK_ENTRY_NAME: name,
            LOGBOOK_ENTRY_MESSAGE: f"fired event '{data}'",
        }

    @callback
    def async_describe_deconz_event(event: Event) -> dict[str, str]:
        """Describe deCONZ logbook event."""
        if device := device_registry.devices.get(event.data[ATTR_DEVICE_ID]):
            deconz_event = _get_deconz_event_from_device(hass, device)
            name = deconz_event.device.name
        else:
            deconz_event = None
            name = event.data[CONF_ID]

        action = None
        interface = None
        data = event.data.get(CONF_EVENT) or event.data.get(CONF_GESTURE, "")

        if data and deconz_event and deconz_event.device.model_id in REMOTES:
            action, interface = _get_device_event_description(
                deconz_event.device.model_id, data
            )

        # Unknown event
        if not data:
            return {
                LOGBOOK_ENTRY_NAME: name,
                LOGBOOK_ENTRY_MESSAGE: "fired an unknown event",
            }

        # No device event match
        if not action:
            return {
                LOGBOOK_ENTRY_NAME: name,
                LOGBOOK_ENTRY_MESSAGE: f"fired event '{data}'",
            }

        # Gesture event
        if not interface:
            return {
                LOGBOOK_ENTRY_NAME: name,
                LOGBOOK_ENTRY_MESSAGE: f"fired event '{ACTIONS[action]}'",
            }

        return {
            LOGBOOK_ENTRY_NAME: name,
            LOGBOOK_ENTRY_MESSAGE: (
                f"'{ACTIONS[action]}' event for '{INTERFACES[interface]}' was fired"
            ),
        }

    async_describe_event(
        DECONZ_DOMAIN, CONF_DECONZ_ALARM_EVENT, async_describe_deconz_alarm_event
    )
    async_describe_event(DECONZ_DOMAIN, CONF_DECONZ_EVENT, async_describe_deconz_event)
