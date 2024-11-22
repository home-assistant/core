"""The constants of the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum, unique
from typing import Final

DOMAIN: Final = "evohome"

STORAGE_VER: Final = 1
STORAGE_KEY: Final = DOMAIN

# The Parent's (i.e. TCS, Controller) operating mode is one of:
EVO_RESET: Final = "AutoWithReset"
EVO_AUTO: Final = "Auto"
EVO_AUTOECO: Final = "AutoWithEco"
EVO_AWAY: Final = "Away"
EVO_DAYOFF: Final = "DayOff"
EVO_CUSTOM: Final = "Custom"
EVO_HEATOFF: Final = "HeatingOff"

# The Children's (i.e. Dhw, Zone) operating mode is one of:
EVO_FOLLOW: Final = "FollowSchedule"  # the operating mode is 'inherited' from the TCS
EVO_TEMPOVER: Final = "TemporaryOverride"
EVO_PERMOVER: Final = "PermanentOverride"

# These two are used only to help prevent E501 (line too long) violations
GWS: Final = "gateways"
TCS: Final = "temperatureControlSystems"

UTC_OFFSET: Final = "currentOffsetMinutes"

CONF_LOCATION_IDX: Final = "location_idx"

ACCESS_TOKEN: Final = "access_token"
ACCESS_TOKEN_EXPIRES: Final = "access_token_expires"
REFRESH_TOKEN: Final = "refresh_token"
USER_DATA: Final = "user_data"

SCAN_INTERVAL_DEFAULT: Final = timedelta(seconds=300)
SCAN_INTERVAL_MINIMUM: Final = timedelta(seconds=60)

ATTR_SYSTEM_MODE: Final = "mode"
ATTR_DURATION_DAYS: Final = "period"
ATTR_DURATION_HOURS: Final = "duration"

ATTR_ZONE_TEMP: Final = "setpoint"
ATTR_DURATION_UNTIL: Final = "duration"


@unique
class EvoService(StrEnum):
    """The Evohome services."""

    REFRESH_SYSTEM = "refresh_system"
    SET_SYSTEM_MODE = "set_system_mode"
    RESET_SYSTEM = "reset_system"
    SET_ZONE_OVERRIDE = "set_zone_override"
    RESET_ZONE_OVERRIDE = "clear_zone_override"
