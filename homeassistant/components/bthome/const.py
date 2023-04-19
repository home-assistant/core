"""Constants for the BTHome Bluetooth integration."""
from __future__ import annotations

from typing import Final, TypedDict

DOMAIN = "bthome"

CONF_BIND_KEY: Final = "bind_key"
CONF_KNOWN_EVENTS: Final = "known_events"

EVENT_TYPE: Final = "event_type"
EVENT_CLASS: Final = "event_class"
BTHOME_BLE_EVENT: Final = "bthome_ble_event"


EVENT_CLASS_BUTTON: Final = "button"
EVENT_CLASS_DIMMER: Final = "dimmer"

CONF_EVENT_CLASS: Final = "event_class"


class BTHomeBleEvent(TypedDict):
    """BTHome BLE event data."""

    device_id: str
    address: str
    event_class: str  # ie 'button'
    event_type: str  # ie 'press'
