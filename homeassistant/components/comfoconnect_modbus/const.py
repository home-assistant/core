"""Constants for the Zehnder ComfoConnect PRO integration."""

from typing import Literal

DOMAIN = "comfoconnect_modbus"
MANUFACTURER = "Zehnder"
MODEL = "ComfoConnect PRO"

DEFAULT_NAME = "ComfoAir"
DEFAULT_BAUDRATE = 19200
DEFAULT_PARITY = "even"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
SCAN_INTERVAL = 30

# `BAUDRATES` lists what the gateway's Protocols and services page offers.
BAUDRATES = (
    9600,
    14400,
    19200,
    28800,
    38400,
    57600,
    115200,
    128000,
    230400,
    256000,
    460800,
    921600,
)
PARITIES: dict[str, Literal["E", "O", "N"]] = {"even": "E", "odd": "O", "none": "N"}

CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_UNIT_ID = "unit_id"

TYPE_SERIAL = "serial"
TYPE_TCP = "tcp"
