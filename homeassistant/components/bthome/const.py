"""Constants for the BTHome Bluetooth integration."""
from __future__ import annotations

from typing import Final, TypedDict

DOMAIN = "bthome"


CONF_DEVICE_KEY: Final = "device_key"
CONF_EVENT_PROPERTIES: Final = "event_properties"
EVENT_PROPERTIES: Final = "event_properties"
EVENT_TYPE: Final = "event_type"
BTHOME_BLE_EVENT: Final = "bthome_ble_event"


class BTHomeBleEvent(TypedDict):
    """BTHome BLE event data."""

    device_id: str
    address: str
    event_type: str
    event_properties: dict[str, str | int | float | None] | None
