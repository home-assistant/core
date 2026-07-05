"""Core constants for the Greencell EVSE Home Assistant integration."""

from typing import Final

# Greencell constants

DOMAIN = "greencell"
MANUFACTURER: Final = "Greencell"

# Maximal current configuration

DEFAULT_MIN_CURRENT = 6
DEFAULT_MAX_CURRENT_OTHER = 16
DEFAULT_MAX_CURRENT_HABU_DEN = 32

# Topics

GREENCELL_BROADCAST_TOPIC = "/greencell/broadcast"
GREENCELL_DISC_TOPIC = "/greencell/broadcast/device"

# Device names

GREENCELL_HABU_DEN = "Habu Den"
GREENCELL_OTHER_DEVICE = "Greencell Device"

# Other constants

DISCOVERY_MIN_TIMEOUT = 5.0
DISCOVERY_TIMEOUT = 30.0
SET_CURRENT_RETRY_TIME = 15
CONF_SERIAL_NUMBER = "serial_number"
