"""Constants for the SMLIGHT Zigbee integration."""

from datetime import timedelta
import logging

DOMAIN = "smlight"

ATTR_MANUFACTURER = "SMLIGHT"
DATA_COORDINATOR = "data"
FIRMWARE_COORDINATOR = "firmware"

SCAN_FIRMWARE_INTERVAL = timedelta(hours=6)
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=300)
SCAN_INTERNET_INTERVAL = timedelta(minutes=15)
UPTIME_DEVIATION = timedelta(seconds=5)
