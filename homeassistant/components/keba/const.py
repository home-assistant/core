"""Constants for the KEBA charging station integration."""

from enum import StrEnum

DOMAIN = "keba"


class KebaService(StrEnum):
    """Store keys for KEBA services."""

    REQUEST_DATA = "request_data"
    AUTHORIZE = "authorize"
    DEAUTHORIZE = "deauthorize"
    SET_ENERGY = "set_energy"
    SET_CURRENT = "set_current"
    ENABLE = "enable"
    DISABLE = "disable"
    SET_FAILSAFE = "set_failsafe"


class KebaServiceArgument(StrEnum):
    """Store keys for KEBA service arguments."""

    ENERGY = "energy"
    CURRENT = "current"
    FAILSAFE_TIMEOUT = "failsafe_timeout"
    FAILSAFE_FALLBACK = "failsafe_fallback"
    FAILSAFE_PERSIST = "failsafe_persist"
