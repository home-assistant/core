"""Constants for the Sofar Inverter Modbus integration — distinct from sofar_modbus's own const module (the PyPI library's bitmasks/register tables)."""

DOMAIN = "sofar_modbus"
ATTR_MANUFACTURER = "Sofar Solar"

DEFAULT_NAME = "Sofar"
DEFAULT_PORT = 502
DEFAULT_MODBUS_ADDR = 1
DEFAULT_SCAN_INTERVAL = 5

CONF_MODBUS_ADDR = "modbus_addr"
CONF_READ_EPS = "read_eps"
