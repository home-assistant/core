"""Constants for Radarr."""
import logging

from typing_extensions import Final

DOMAIN: Final = "radarr"

# Defaults
DEFAULT_NAME = "Radarr"
DEFAULT_URL = "http://172.17.0.1:7878"

LOGGER = logging.getLogger(__package__)
