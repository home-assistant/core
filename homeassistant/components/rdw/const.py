"""Constants for the RDW integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "rdw"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

ENTRY_TYPE_SERVICE: Final = "service"
CONF_LICENSE_PLATE: Final = "license_plate"
