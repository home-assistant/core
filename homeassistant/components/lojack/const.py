"""Constants for the LoJack integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "lojack"

LOGGER = logging.getLogger(__package__)

# Default polling interval in minutes
DEFAULT_UPDATE_INTERVAL: Final = 5

# Thresholds
MOVEMENT_SPEED_THRESHOLD: Final = 0.5  # mph - minimum speed to consider vehicle moving

# Extra state attributes for device tracker
ATTR_ADDRESS: Final = "address"
ATTR_GPS_ACCURACY: Final = "gps_accuracy"
ATTR_HEADING: Final = "heading"
