"""Constants for the Combined Energy integration."""
from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final[str] = "combined_energy"

LOGGER = logging.getLogger(__package__)

# Data for Combined Energy requests.
DATA_API_CLIENT: Final[str] = "api_client"
DATA_LOG_SESSION: Final[str] = "log_session"
DATA_INSTALLATION: Final[str] = "installation"

# Config for combined energy requests.
CONF_INSTALLATION_ID: Final[str] = "installation_id"
DEFAULT_NAME: Final[str] = "Combined Energy"

CONNECTIVITY_UPDATE_DELAY: Final[timedelta] = timedelta(seconds=30)
LOG_SESSION_REFRESH_DELAY: Final[timedelta] = timedelta(minutes=10)
READINGS_UPDATE_DELAY: Final[timedelta] = timedelta(minutes=1)

# Increment size in seconds; Valid values are 5/300/1800 (5s/5m/30m)
READINGS_INCREMENT: Final[int] = 5
READINGS_INITIAL_DELTA: Final[timedelta] = timedelta(seconds=40)
