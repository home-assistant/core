"""Constants for the Sofar integration."""

DOMAIN = "sofar"
ATTR_MANUFACTURER = "Sofar Solar"

DEFAULT_NAME = "Sofar"
DEFAULT_BAUDRATE = 9600
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
SCAN_INTERVAL = 5
SETTINGS_SCAN_INTERVAL = 60

CONF_BAUDRATE = "baudrate"
CONF_UNIT_ID = "unit_id"

HAS_FAULT_LOG = "has_fault_log"
LAST_HANDLED_FAULT = "last_handled_fault"

METER_ENERGY = "meter_energy"

TYPE_SERIAL = "serial"
TYPE_TCP = "tcp"
