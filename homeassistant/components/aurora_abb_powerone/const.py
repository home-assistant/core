"""Constants for the Aurora ABB PowerOne integration."""

from datetime import timedelta

DOMAIN = "aurora_abb_powerone"

# Min max addresses and default according to here:
# https://library.e.abb.com/public/e57212c407344a16b4644cee73492b39/PVI-3.0_3.6_4.2-TL-OUTD-Product%20manual%20EN-RevB(M000016BG).pdf

INVERTER_SERIAL_ADDRESS_MIN = 2
INVERTER_SERIAL_ADDRESS_MAX = 64
INVERTER_SERIAL_ADDRESS_DEFAULT = 2

SCAN_INTERVAL = timedelta(seconds=30)

DEFAULT_INTEGRATION_TITLE = "PhotoVoltaic Inverters"
DEFAULT_DEVICE_NAME = "Solar Inverter"

DEVICES = "devices"
MANUFACTURER = "ABB"

ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_ID = "device_id"
ATTR_MODEL = "model"
ATTR_FIRMWARE = "firmware"

TRANSPORT_SERIAL = "serial"
TRANSPORT_TCP = "tcp"

TCP_PORT_DEFAULT = 502

CONF_TRANSPORT = "transport"
CONF_SERIAL_COMPORT = "serial_comport"
CONF_TCP_HOST = "tcp_host"
CONF_TCP_PORT = "tcp_port"
CONF_INVERTER_SERIAL_ADDRESS = "inverter_serial_address"
