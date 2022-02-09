"""Constants for the Elgato Light integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

# Integration domain
DOMAIN: Final = "elgato"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)

# Attributes
ATTR_ON = "on"

# Services
SERVICE_IDENTIFY = "identify"
