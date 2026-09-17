"""Constants for the IONT integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "iont"
LOGGER = logging.getLogger(__package__)

MANUFACTURER: Final = "IONT"
DEFAULT_NAME: Final = "IONT charger"

# The charger listens on the standard Modbus TCP port and answers on any unit
# ID, so neither is worth asking for beyond the port.
DEFAULT_PORT: Final = 502
UNIT_ID: Final = 1

# Local Modbus is cheap to read, and an automation steering the charger on
# solar surplus wants numbers that are seconds old, not minutes.
SCAN_INTERVAL: Final = timedelta(seconds=10)
