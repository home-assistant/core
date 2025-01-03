"""Constants for the edimax integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

# Integration domain
DOMAIN: Final = "edimax"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)

DEFAULT_NAME: Final = "Edimax Smart Plug"
MANUFACTURER: Final = "Edimax"

DEFAULT_USER_NAME = "admin"
DEFAULT_PASSWORD = 1234
