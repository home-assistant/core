"""Constants for the BIR integration."""

from datetime import timedelta
import logging
from typing import Final

from pybirno.const import WASTE_TYPE_MAP

DOMAIN: Final = "bir"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

# Known waste types returned by pybirno
WASTE_TYPES: Final[set[str]] = set(WASTE_TYPE_MAP.values())

# Config keys
CONF_PROPERTY_ID: Final = "property_id"
