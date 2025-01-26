"""Constants for the Powerfox integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "powerfox"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=1)
