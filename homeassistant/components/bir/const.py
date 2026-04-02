"""Constants for the BIR integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "bir"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

# Known waste types returned by pybirno
WASTE_TYPES: Final[set[str]] = {
    "mixed_waste",
    "paper_and_plastic",
    "food_waste",
    "glass_and_metal_packaging",
}

# Config keys
CONF_PROPERTY_ID: Final = "property_id"
