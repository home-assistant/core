"""Constants for the Garages Amsterdam integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "garages_amsterdam"
ATTRIBUTION = f'{"Data provided by municipality of Amsterdam"}'

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=10)
