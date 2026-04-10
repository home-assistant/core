"""Constants for the Powerfox Local integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "powerfox_local"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=5)
