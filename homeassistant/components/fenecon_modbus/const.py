"""Constants for the Fenecon Modbus integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "fenecon_modbus"
LOGGER = logging.getLogger(__package__)

CONF_UNIT_ID: Final = "unit_id"

SCAN_INTERVAL = timedelta(seconds=10)
