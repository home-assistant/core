"""Constants for the Fumis integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "fumis"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=30)
