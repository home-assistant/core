"""Constants for the aWATTar integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "awattar"
CONF_COUNTRY: Final = "awattar_country"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(hours=1)

COUNTRY_TO_CODE = {"Austria": "AT", "Germany": "DE"}

SERVICE_TYPE_DEVICE_NAMES = {
    "energy": "Energy market price",
}
