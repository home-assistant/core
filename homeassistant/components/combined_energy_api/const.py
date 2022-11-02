"""Constants for the Combined Energy API integration."""
from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final[str] = "combined_energy_api"

LOGGER = logging.getLogger(__package__)

CONF_INSTALLATION_ID: Final[str] = "installation_id"
DEFAULT_NAME: Final[str] = "Combined Energy API"

SCAN_INTERVAL: Final[timedelta] = timedelta(seconds=30)
