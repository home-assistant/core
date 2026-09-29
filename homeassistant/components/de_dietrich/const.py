"""Constants for the De Dietrich integration."""

from typing import Final

DOMAIN = "de_dietrich"
ATTR_MANUFACTURER = "De Dietrich"
DEFAULT_NAME = "De Dietrich"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 10
SCAN_INTERVAL = 15
CONF_UNIT_ID = "unit_id"
MODBUS_FRAMER: Final = "rtu"
MESSAGE_SPACING: Final = 0.05
