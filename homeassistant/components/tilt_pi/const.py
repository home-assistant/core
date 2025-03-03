"""Constants for the Tilt Pi integration."""

from datetime import timedelta
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "tilt_pi"
DEFAULT_PORT: Final = 1883
NAME: Final = "Tilt Pi"
SCAN_INTERVAL: Final = timedelta(seconds=60)
