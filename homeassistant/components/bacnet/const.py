"""Constants for the BACnet integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "bacnet"

# Data keys
DATA_CLIENT: Final = "client"
DATA_DEVICES: Final = "devices"
DATA_HUB_ID: Final = "hub_id"

# Config entry types
CONF_ENTRY_TYPE: Final = "entry_type"
ENTRY_TYPE_HUB: Final = "hub"
ENTRY_TYPE_DEVICE: Final = "device"

# Config keys
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_ADDRESS: Final = "device_address"
CONF_INTERFACE: Final = "interface"
CONF_HUB_ID: Final = "hub_id"
CONF_OBJECT_LIST: Final = "object_list"
CONF_SELECTED_OBJECTS: Final = "selected_objects"

DEFAULT_PORT: Final = 47808
DISCOVERY_TIMEOUT: Final = 5
DISCOVERY_INTERVAL: Final = timedelta(minutes=5)
COV_LIFETIME: Final = 300
COV_RENEW_INTERVAL: Final = timedelta(seconds=240)

UPDATE_INTERVAL: Final = timedelta(seconds=60)
REDISCOVERY_INTERVAL: Final = timedelta(minutes=5)

# Timeout constants for async operations (in seconds)
TIMEOUT_PROPERTY_READ: Final = 5  # Individual property read timeout
TIMEOUT_PROPERTY_READ_SHORT: Final = 2  # Short timeout for non-critical properties
TIMEOUT_OBJECT_LIST_READ: Final = 10  # Reading full object list
TIMEOUT_COV_GET_VALUE: Final = COV_LIFETIME + 30  # COV notification timeout

MANUFACTURER: Final = "BACnet Device"

# BACnet object types that produce numeric/analog sensor values (read-only)
ANALOG_OBJECT_TYPES: Final = {
    "analog-input",
    "analog-value",
    "large-analog-value",
    "integer-value",
    "positive-integer-value",
    "accumulator",
    "pulse-converter",
}

# BACnet object types that produce multi-state (enum) sensor values (read-only)
MULTISTATE_OBJECT_TYPES: Final = {
    "multi-state-input",
    "multi-state-value",
}

# BACnet output object types (writable)
ANALOG_OUTPUT_OBJECT_TYPE: Final = "analog-output"
BINARY_OUTPUT_OBJECT_TYPE: Final = "binary-output"
MULTISTATE_OUTPUT_OBJECT_TYPE: Final = "multi-state-output"

# BACnet write priority (16 = lowest, manual-life-safety = 1)
WRITE_PRIORITY: Final = 16
