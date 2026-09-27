"""Constants for the Autarco integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "autarco"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=5)
