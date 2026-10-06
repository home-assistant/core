"""Constants for the LoJack integration."""

import logging
from typing import Final

DOMAIN: Final = "lojack"

LOGGER = logging.getLogger(__package__)

# Default polling interval (in minutes)
DEFAULT_UPDATE_INTERVAL: Final = 5

# Minimum speed (in the API's speed unit, mph) for a vehicle to be considered moving
MOVEMENT_SPEED_THRESHOLD: Final = 0.5
