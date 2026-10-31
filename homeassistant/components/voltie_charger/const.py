"""Constants for the Voltie Charger integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "voltie_charger"
LOGGER = logging.getLogger(__package__)

MANUFACTURER: Final = "Voltie"

DATA_SCAN_INTERVAL = timedelta(seconds=30)

# Older HTTP API versions lack endpoints and settings the integration needs
MIN_API_VERSION: Final = 5
