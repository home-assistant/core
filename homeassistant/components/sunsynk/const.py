"""Constants for the Sunsynk integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "sunsynk"
LOGGER = logging.getLogger(__package__)

# The inverter uploads new data to the Sunsynk cloud every five minutes.
SCAN_INTERVAL = timedelta(minutes=5)
