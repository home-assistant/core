"""Constants for the SMLIGHT Zigbee integration."""

from datetime import timedelta
from enum import StrEnum
import logging

from pysmlight.const import ZB_TYPES

DOMAIN = "smlight"

ATTR_MANUFACTURER = "SMLIGHT"
DATA_COORDINATOR = "data"
FIRMWARE_COORDINATOR = "firmware"

SCAN_FIRMWARE_INTERVAL = timedelta(hours=24)
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=300)
SCAN_INTERNET_INTERVAL = timedelta(minutes=15)
UPTIME_DEVIATION = timedelta(seconds=5)

CONF_BLE_SCANNER_MODE = "ble_scanner_mode"


class BLEScannerMode(StrEnum):
    """BLE scanner mode."""

    DISABLED = "disabled"
    AUTO = "auto"
    ACTIVE = "active"
    PASSIVE = "passive"


ZWAVE_TYPES = tuple(k for k, v in ZB_TYPES.items() if v.lower().startswith("zwave"))
