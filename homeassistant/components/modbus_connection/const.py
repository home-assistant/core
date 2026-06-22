"""Constants for the Modbus Connection integration."""

from typing import Final

DOMAIN: Final = "modbus_connection"

# Transport selection (stored under homeassistant.const.CONF_TYPE).
CONNECTION_TCP: Final = "tcp"
CONNECTION_SERIAL: Final = "serial"

# Serial-only options.
CONF_BAUDRATE: Final = "baudrate"
CONF_BYTESIZE: Final = "bytesize"
CONF_PARITY: Final = "parity"
CONF_STOPBITS: Final = "stopbits"

DEFAULT_PORT: Final = 502
DEFAULT_BAUDRATE: Final = 9600
DEFAULT_BYTESIZE: Final = 8
DEFAULT_PARITY: Final = "N"
DEFAULT_STOPBITS: Final = 1
