"""Constants for Radarr."""
import logging

from typing_extensions import Final

DOMAIN: Final = "radarr"

# Config Keys
CONF_UPCOMING_DAYS = "upcoming_days"

# Defaults
DEFAULT_NAME = "Radarr"
DEFAULT_URL = "http://127.0.0.1:7878"
DEFAULT_UPCOMING_DAYS = 7

LOGGER = logging.getLogger(__package__)
