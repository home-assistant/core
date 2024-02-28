"""Constants for the Xiaomi Bluetooth integration."""
from __future__ import annotations

from typing import Final, TypedDict

DOMAIN = "xiaomi_ble"


CONF_DISCOVERED_EVENT_CLASSES: Final = "known_events"
CONF_EVENT_PROPERTIES: Final = "event_properties"
CONF_EVENT_CLASS: Final = "event_class"
CONF_SLEEPY_DEVICE: Final = "sleepy_device"
CONF_SUBTYPE: Final = "subtype"

EVENT_CLASS: Final = "event_class"
EVENT_TYPE: Final = "event_type"
EVENT_SUBTYPE: Final = "event_subtype"
EVENT_PROPERTIES: Final = "event_properties"
XIAOMI_BLE_EVENT: Final = "xiaomi_ble_event"

EVENT_CLASS_BUTTON: Final = "button"
EVENT_CLASS_DIMMER: Final = "dimmer"
EVENT_CLASS_MOTION: Final = "motion"
EVENT_CLASS_CUBE: Final = "cube"

BUTTON: Final = "button"
CUBE: Final = "cube"
DIMMER: Final = "dimmer"
DOUBLE_BUTTON: Final = "double_button"
TRIPPLE_BUTTON: Final = "tripple_button"
REMOTE: Final = "remote"
REMOTE_FAN: Final = "remote_fan"
REMOTE_VENFAN: Final = "remote_ventilator_fan"
REMOTE_BATHROOM: Final = "remote_bathroom"
MOTION: Final = "motion"

BUTTON_PRESS: Final = "button_press"
BUTTON_PRESS_LONG: Final = "button_press_long"
BUTTON_PRESS_DOUBLE_LONG: Final = "button_press_double_long"
DOUBLE_BUTTON_PRESS_DOUBLE_LONG: Final = "double_button_press_double_long"
TRIPPLE_BUTTON_PRESS_DOUBLE_LONG: Final = "tripple_button_press_double_long"
MOTION_DEVICE: Final = "motion_device"


class XiaomiBleEvent(TypedDict):
    """Xiaomi BLE event data."""

    device_id: str
    address: str
    event_class: str  # ie 'button'
    event_type: str  # ie 'press'
    event_properties: dict[str, str | int | float | None] | None
