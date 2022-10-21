"""Describe lutron_caseta logbook events."""
from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.const import ATTR_DEVICE_ID
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
from .device_trigger import (
    LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP,
    _reverse_dict,
    get_lutron_data_by_dr_id,
)

_LOGGER = logging.getLogger(__name__)


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
        device_id = data[ATTR_DEVICE_ID]
        lutron_data = get_lutron_data_by_dr_id(hass, device_id)
        keypad_device = lutron_data.dr_id_to_keypad_map.get(device_id)
        keypad_device_id = keypad_device["device_id"]

        keypad_button_maps = lutron_data.keypad_button_maps

        if not (button_map := LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(device_type)):
            if fwd_button_map := keypad_button_maps.get(keypad_device_id):
                button_map = _reverse_dict(fwd_button_map)

        if button_map is None:
            return {
                LOGBOOK_ENTRY_NAME: f"{data[ATTR_AREA_NAME]} {data[ATTR_DEVICE_NAME]}",
                LOGBOOK_ENTRY_MESSAGE: f"{data[ATTR_ACTION]} Error retrieving button description",
            }

        button_description = button_map.get(leap_button_number)
        return {
            LOGBOOK_ENTRY_NAME: f"{data[ATTR_AREA_NAME]} {data[ATTR_DEVICE_NAME]}",
            LOGBOOK_ENTRY_MESSAGE: f"{data[ATTR_ACTION]} {button_description}",
        }

    async_describe_event(
        DOMAIN, LUTRON_CASETA_BUTTON_EVENT, async_describe_button_event
    )
