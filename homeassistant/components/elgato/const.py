"""Constants for the Elgato Light integration."""

from datetime import timedelta
import logging
from typing import Final

# Integration domain
DOMAIN: Final = "elgato"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)

# Elgato publishes firmware a handful of times a year, bundled with a new
# Control Center release. Asking more often than this buys nothing.
FIRMWARE_SCAN_INTERVAL = timedelta(hours=12)

# Attributes
ATTR_ON = "on"
