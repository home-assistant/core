"""Constants for the GridX integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "gridx"

LOGGER = logging.getLogger(__package__)

# Only the EON Home realm remains; the Viessmann realm was shut down end of 2025.
OEM: Final = "eon-home"

API_BASE_URL: Final = "https://api.gridx.de"

LIVE_UPDATE_INTERVAL = timedelta(seconds=30)
