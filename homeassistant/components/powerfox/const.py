"""Constants for the Powerfox integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "powerfox"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)
