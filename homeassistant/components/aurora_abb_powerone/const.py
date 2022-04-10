"""Constants for the Aurora ABB PowerOne integration."""

DOMAIN = "aurora_abb_powerone"

# Min max addresses and default according to here:
# https://library.e.abb.com/public/e57212c407344a16b4644cee73492b39/PVI-3.0_3.6_4.2-TL-OUTD-Product%20manual%20EN-RevB(M000016BG).pdf

MIN_ADDRESS = 2
MAX_ADDRESS = 63
DEFAULT_ADDRESS = 2

DEFAULT_INTEGRATION_TITLE = "PhotoVoltaic Inverters"
DEFAULT_DEVICE_NAME = "Solar Inverter"

DEVICES = "devices"
MANUFACTURER = "ABB"

ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_ID = "device_id"
ATTR_SERIAL_NUMBER = "serial_number"
ATTR_MODEL = "model"
ATTR_FIRMWARE = "firmware"
