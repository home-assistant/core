"""Constants for Radarr."""
import logging
from typing import Final

CONF_USE_ADDON = "use_addon"

DOMAIN: Final = "radarr"

# Defaults
DEFAULT_NAME = "Radarr"
DEFAULT_URL = "http://127.0.0.1:7878"

LOGGER = logging.getLogger(__package__)
