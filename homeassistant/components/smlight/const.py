"""Constants for the SMLIGHT Zigbee integration."""

from datetime import timedelta
import logging

DOMAIN = "smlight"

ATTR_MANUFACTURER = "SMLIGHT"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=300)
UPTIME_DEVIATION = timedelta(seconds=5)
