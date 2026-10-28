"""Constants for the aerosmart integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "aerosmart"

CONF_BAUDRATE: Final = "baudrate"
CONF_UNIT_VENTILATION: Final = "unit_ventilation"
CONF_UNIT_HEAT_PUMP: Final = "unit_heat_pump"

DEFAULT_BAUDRATE: Final = 9600
DEFAULT_PORT: Final = 502

TYPE_SERIAL: Final = "serial"
TYPE_TCP: Final = "tcp"

# The installation this library was transcribed from uses unit 1 for the
# ventilation controller and unit 2 for the heat pump; both are configurable
# in case another installation differs.
DEFAULT_UNIT_VENTILATION: Final = 1
DEFAULT_UNIT_HEAT_PUMP: Final = 2

# One 32-bit datapoint per request and the device library's required 300ms line
# quiet time put the operating-data poll above 30 seconds. Keep enough headroom
# that the shared gateway is idle between polls.
READINGS_SCAN_INTERVAL: Final = timedelta(seconds=60)

# Filter counters and user settings change slowly. Writes refresh this
# coordinator immediately, so external changes are the only reason to poll it
# periodically.
SETTINGS_SCAN_INTERVAL: Final = timedelta(minutes=10)
