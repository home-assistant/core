"""Constants for the Xiaomi Bluetooth integration."""
from __future__ import annotations

from typing import TypedDict

DOMAIN = "xiaomi_ble"


XIAOMI_BLE_EVENT = "xiaomi_ble_event"


class XiaomiBleEvent(TypedDict):
    """Xiaomi BLE event data."""

    device_id: str
    address: str
    event_type: str
    event_properties: dict[str, str | int | float | None] | None
