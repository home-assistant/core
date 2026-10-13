"""Constants for the Sunsynk integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "sunsynk"
LOGGER = logging.getLogger(__package__)

# How a config entry connects to its inverters.
TYPE_CLOUD: Final = "cloud"
TYPE_MODBUS: Final = "modbus"

CONF_UNIT_ID: Final = "unit_id"
DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1

# The inverter uploads new data to the Sunsynk cloud every five minutes.
SCAN_INTERVAL = timedelta(minutes=5)

# A full Modbus poll reads approximately 150 registers. At 9600 baud, this
# takes approximately 0.5 seconds.
MODBUS_SCAN_INTERVAL = timedelta(seconds=10)
