"""Constants used by Advantage Air integration."""

from enum import StrEnum

DOMAIN = "advantage_air"
ADVANTAGE_AIR_RETRY = 10
ADVANTAGE_AIR_STATE_OPEN = "open"
ADVANTAGE_AIR_STATE_CLOSE = "close"
ADVANTAGE_AIR_STATE_ON = "on"
ADVANTAGE_AIR_STATE_OFF = "off"
ADVANTAGE_AIR_AUTOFAN_ENABLED = "aaAutoFanModeEnabled"
ADVANTAGE_AIR_NIGHT_MODE_ENABLED = "quietNightModeEnabled"


class AdvantageAirService(StrEnum):
    """Store keys for Advantage Air services."""

    SET_TIME_TO = "set_time_to"


class AdvantageAirServiceArgument(StrEnum):
    """Store keys for Advantage Air service arguments."""

    MINUTES = "minutes"
