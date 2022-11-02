"""Constants for the Combined Energy API integration."""
from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final[str] = "combined_energy_api"

LOGGER = logging.getLogger(__package__)

DATA_API_CLIENT = "api_client"

# Config for combined energy api requests.
CONF_INSTALLATION_ID: Final[str] = "installation_id"
DEFAULT_NAME: Final[str] = "Combined Energy API"

CONNECTIVITY_UPDATE_DELAY: Final[timedelta] = timedelta(seconds=30)
READINGS_UPDATE_DELAY: Final[timedelta] = timedelta(seconds=30)

READINGS_INCREMENT: Final[int] = 5
