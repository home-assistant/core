"""Constants for the Garages Amsterdam integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "garages_amsterdam"
ATTRIBUTION = "Data provided by municipality of Amsterdam"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=10)
