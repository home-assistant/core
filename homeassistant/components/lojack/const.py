"""Constants for the LoJack integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "lojack"

LOGGER = logging.getLogger(__package__)

# Default polling interval (in minutes)
DEFAULT_UPDATE_INTERVAL: Final = 5

# Extra state attributes for device tracker
ATTR_ADDRESS: Final = "address"
ATTR_HEADING: Final = "heading"
ATTR_LAST_POLLED: Final = "last_polled"
