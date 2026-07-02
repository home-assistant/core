"""Constants for the LoJack integration."""

import logging
from typing import Final

DOMAIN: Final = "lojack"

LOGGER = logging.getLogger(__package__)

# Default polling interval (in minutes)
DEFAULT_UPDATE_INTERVAL: Final = 5
