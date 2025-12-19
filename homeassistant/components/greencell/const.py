"""Core constants and enumerations for the Greencell EVSE Home Assistant integration.

Contents:
- EvseTypeStringEnum: base enum class generating string values from member names.
- EvseStateEnum: valid EVSE states (IDLE, CONNECTED, WAITING_FOR_CAR, CHARGING, FINISHED, ERROR_CAR, ERROR_EVSE, UNKNOWN).
- GreencellHaAccessLevelEnum: Home Assistant access levels (DISABLED, READ_ONLY, EXECUTE, UNAVAILABLE).
- DOMAIN and MANUFACTURER identifiers for the integration.
- Default current limits: DEFAULT_MIN_CURRENT, DEFAULT_MAX_CURRENT_OTHER, DEFAULT_MAX_CURRENT_HABU_DEN.
- MQTT topics for broadcast and discovery.
- Device name templates: GREENCELL_HABU_DEN, GREENCELL_OTHER_DEVICE.
- Serial number prefix for Habu Den devices.
- Discovery and retry timing constants: DISCOVERY_TIMEOUT, SET_CURRENT_RETRY_TIME.
"""

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

# Runtime data keys
GREENCELL_ACCESS_KEY = "access"
GREENCELL_CURRENT_DATA_KEY = "current_data"
GREENCELL_VOLTAGE_DATA_KEY = "voltage_data"
GREENCELL_POWER_DATA_KEY = "power_data"
GREENCELL_STATE_DATA_KEY = "state_data"

# Other constants

DISCOVERY_MIN_TIMEOUT = 5.0
DISCOVERY_TIMEOUT = 30.0
SET_CURRENT_RETRY_TIME = 15
CONF_SERIAL_NUMBER = "serial_number"
