from typing import Final
from enum import Enum

class EvseStateEnum(Enum):
    IDLE = 1,
    CONNECTED = 2,
    WAITING_FOR_CAR = 3,
    CHARGING = 4,
    FINISHED = 5,
    ERROR_CAR = 6,
    ERROR_EVSE = 7,
    UNKNOWN = 8

class GreencellHaAccessLevelEnum(Enum):
    DISABLED = 0,
    READ_ONLY = 1,
    EXECUTE = 2,
    OFFLINE = 3

# Greencell constants

DOMAIN = 'greencell'
MANUFACTURER: Final = 'Greencell'

# Maximal current configuration

DEFAULT_MIN_CURRENT = 6
DEFAULT_MAX_CURRENT_OTHER = 16
DEFAULT_MAX_CURRENT_HABU_DEN = 32

# Topics

GREENCELL_BROADCAST_TOPIC = '/greencell/broadcast'
GREENCELL_DISC_TOPIC = '/greencell/broadcast/device'

# Device names

GREENCELL_HABU_DEN = 'Habu Den'
GREENCELL_OTHER_DEVICE = 'Greencell Device'

# Serial prefixes

GREENCELL_HABU_DEN_SERIAL_PREFIX = 'EVGC02'

# Other constants

DISCOVERY_TIMEOUT = 30.0
