"""Constants for the De Dietrich integration."""

from typing import Final

DOMAIN = "de_dietrich"
ATTR_MANUFACTURER = "De Dietrich"
DEFAULT_NAME = "De Dietrich"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 10
SCAN_INTERVAL = 15
CONF_UNIT_ID = "unit_id"
CONF_SYSTEM = "system"
SYSTEM_DIEMATIC_3 = "diematic_3"
SYSTEM_DIEMATIC_4 = "diematic_4"
SYSTEM_ISYSTEM = "isystem"
MODBUS_FRAMER: Final = "rtu"
MESSAGE_SPACING: Final = 0.05
