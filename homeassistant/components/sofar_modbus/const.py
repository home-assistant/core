"""Constants for the Sofar Inverter Modbus integration.

Integration-level config keys and defaults only. Distinct from sofar_modbus's
own const module (the PyPI library), which holds the device library's
bitmasks and register-map tables.
"""

DOMAIN = "sofar_modbus"
ATTR_MANUFACTURER = "Sofar Solar"

DEFAULT_NAME = "Sofar"
DEFAULT_PORT = 502
DEFAULT_MODBUS_ADDR = 1
DEFAULT_SCAN_INTERVAL = 5

CONF_MODBUS_ADDR = "modbus_addr"
CONF_READ_EPS = "read_eps"
