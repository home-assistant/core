"""Constants for the BTHome Bluetooth integration."""
from __future__ import annotations

from typing import Final, TypedDict

DOMAIN = "bthome"

CONF_BINDKEY: Final = "bindkey"
CONF_DISCOVERED_EVENT_CLASSES: Final = "known_events"
CONF_SLEEPY_DEVICE: Final = "sleepy_device"
CONF_SUBTYPE: Final = "subtype"

EVENT_TYPE: Final = "event_type"
EVENT_CLASS: Final = "event_class"
EVENT_PROPERTIES: Final = "event_properties"
BTHOME_BLE_EVENT: Final = "bthome_ble_event"


EVENT_CLASS_BUTTON: Final = "button"
EVENT_CLASS_DIMMER: Final = "dimmer"

CONF_EVENT_CLASS: Final = "event_class"
CONF_EVENT_PROPERTIES: Final = "event_properties"


class BTHomeBleEvent(TypedDict):
    """BTHome BLE event data."""

    device_id: str
    address: str
    event_class: str  # ie 'button'
    event_type: str  # ie 'press'
    event_properties: dict[str, str | int | float | None] | None
