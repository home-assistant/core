"""const.py

Core constants and enumerations for the Greencell EVSE Home Assistant integration.

Contents:
- EvseTypeStringEnum: base enum class generating string values from member names.
- EvseStateEnum: valid EVSE states (IDLE, CONNECTED, WAITING_FOR_CAR, CHARGING, FINISHED, ERROR_CAR, ERROR_EVSE, UNKNOWN).
- GreencellHaAccessLevelEnum: Home Assistant access levels (DISABLED, READ_ONLY, EXECUTE, OFFLINE).
- DOMAIN and MANUFACTURER identifiers for the integration.
- Default current limits: DEFAULT_MIN_CURRENT, DEFAULT_MAX_CURRENT_OTHER, DEFAULT_MAX_CURRENT_HABU_DEN.
- MQTT topics for broadcast and discovery.
- Device name templates: GREENCELL_HABU_DEN, GREENCELL_OTHER_DEVICE.
- Serial number prefix for Habu Den devices.
- Discovery and retry timing constants: DISCOVERY_TIMEOUT, SET_CURRENT_RETRY_TIME.
"""

from enum import Enum, auto
from typing import Final


class EvseTypeStringEnum(Enum):
    """Declaration of EVSE types as string enums."""

    def _generate_next_value_(name, start, count, last_values):
        return name


class EvseStateEnum(EvseTypeStringEnum):
    IDLE = auto()
    CONNECTED = auto()
    WAITING_FOR_CAR = auto()
    CHARGING = auto()
    FINISHED = auto()
    ERROR_CAR = auto()
    ERROR_EVSE = auto()
    UNKNOWN = auto()


class GreencellHaAccessLevelEnum(EvseTypeStringEnum):
    DISABLED = auto()
    READ_ONLY = auto()
    EXECUTE = auto()
    OFFLINE = auto()


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

# Serial prefixes

GREENCELL_HABU_DEN_SERIAL_PREFIX = "EVGC02"

# Other constants

DISCOVERY_TIMEOUT = 30.0
SET_CURRENT_RETRY_TIME = 15
