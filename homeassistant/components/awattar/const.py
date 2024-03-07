"""Constants for the aWATTar integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "awattar"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)
