"""The constants of the Evohome integration."""

from __future__ import annotations

from enum import StrEnum, unique
from typing import Final

DOMAIN: Final = "evohome"

STORAGE_VER: Final = 1
STORAGE_KEY: Final = DOMAIN

CONF_LOCATION_IDX: Final = "location_idx"
DEFAULT_LOCATION_IDX: Final = 0

CONF_HIGH_PRECISION: Final = "high_precision"
DEFAULT_HIGH_PRECISION: Final = False

DEFAULT_SCAN_INTERVAL: Final = 60 * 5  # seconds
MAXIMUM_SCAN_INTERVAL: Final = 60 * 15
MINIMUM_SCAN_INTERVAL: Final = 60

USER_DATA: Final = "user_data"

ATTR_PERIOD: Final = "period"  # number of days
ATTR_DURATION: Final = "duration"  # number of minutes, <24h

ATTR_SETPOINT: Final = "setpoint"
ATTR_DURATION_UNTIL: Final = "duration"


@unique
class EvoService(StrEnum):
    """The Evohome services."""

    REFRESH_SYSTEM = "refresh_system"
    SET_SYSTEM_MODE = "set_system_mode"
    RESET_SYSTEM = "reset_system"
    SET_ZONE_OVERRIDE = "set_zone_override"
    RESET_ZONE_OVERRIDE = "clear_zone_override"
