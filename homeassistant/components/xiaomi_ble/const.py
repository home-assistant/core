"""Constants for the Xiaomi Bluetooth integration."""
from __future__ import annotations

from typing import Final, TypedDict

DOMAIN = "xiaomi_ble"


CONF_DISCOVERED_EVENT_CLASSES: Final = "known_events"
CONF_SLEEPY_DEVICE: Final = "sleepy_device"
CONF_EVENT_PROPERTIES: Final = "event_properties"
EVENT_PROPERTIES: Final = "event_properties"
EVENT_TYPE: Final = "event_type"
XIAOMI_BLE_EVENT: Final = "xiaomi_ble_event"


class XiaomiBleEvent(TypedDict):
    """Xiaomi BLE event data."""

    device_id: str
    address: str
    event_class: str  # ie 'button'
    event_type: str  # ie 'press'
    event_properties: dict[str, str | int | float | None] | None
