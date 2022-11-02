"""Constants for the Combined Energy API integration."""
from datetime import timedelta
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

DOMAIN: Final[str] = "combined_energy_api"

SCAN_INTERVAL: Final[timedelta] = timedelta(seconds=30)

CONF_INSTALLATION_ID: Final[str] = "installation_id"
