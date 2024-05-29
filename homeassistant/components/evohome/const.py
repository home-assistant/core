"""The constants of the Evohome integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "evohome"

STORAGE_VER: Final = 1
STORAGE_KEY: Final = DOMAIN

# The Parent's (i.e. TCS, Controller's) operating mode is one of:
EVO_RESET: Final = "AutoWithReset"
EVO_AUTO: Final = "Auto"
EVO_AUTOECO: Final = "AutoWithEco"
EVO_AWAY: Final = "Away"
EVO_DAYOFF: Final = "DayOff"
EVO_CUSTOM: Final = "Custom"
EVO_HEATOFF: Final = "HeatingOff"

# The Children's operating mode is one of:
EVO_FOLLOW: Final = "FollowSchedule"  # the operating mode is 'inherited' from the TCS
EVO_TEMPOVER: Final = "TemporaryOverride"
EVO_PERMOVER: Final = "PermanentOverride"

# These are used only to help prevent E501 (line too long) violations
GWS: Final = "gateways"
TCS: Final = "temperatureControlSystems"

UTC_OFFSET: Final = "currentOffsetMinutes"

CONF_LOCATION_IDX: Final = "location_idx"

ACCESS_TOKEN: Final = "access_token"
ACCESS_TOKEN_EXPIRES: Final = "access_token_expires"
REFRESH_TOKEN: Final = "refresh_token"
USER_DATA: Final = "user_data"
