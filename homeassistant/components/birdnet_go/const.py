"""Constants for the BirdNET-Go integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "birdnet_go"
LOGGER = logging.getLogger(__package__)

DEFAULT_NAME: Final = "BirdNET-Go"
DEFAULT_PORT: Final = 8080
SCAN_INTERVAL: Final = timedelta(seconds=30)
