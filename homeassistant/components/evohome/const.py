"""The constants of the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum, unique
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import EvoData

DOMAIN: Final = "evohome"
EVOHOME_DATA: HassKey[EvoData] = HassKey(DOMAIN)

STORAGE_VER: Final = 1
STORAGE_KEY: Final = DOMAIN

CONF_LOCATION_IDX: Final = "location_idx"

USER_DATA: Final = "user_data"

SCAN_INTERVAL_DEFAULT: Final = timedelta(seconds=300)
SCAN_INTERVAL_MINIMUM: Final = timedelta(seconds=60)

ATTR_DHW_STATE: Final = "state"
ATTR_DURATION: Final = "duration"  # number of minutes, <24h
ATTR_PERIOD: Final = "period"  # number of days
ATTR_SETPOINT: Final = "setpoint"


@unique
class EvoService(StrEnum):
    """The Evohome services."""

    # Domain-level services (controller/TCS)
    REFRESH_SYSTEM = "refresh_system"
    SET_SYSTEM_MODE = "set_system_mode"
    RESET_SYSTEM = "reset_system"

    # Entity services (zones)
    CLEAR_ZONE_OVERRIDE = "clear_zone_override"
    SET_ZONE_OVERRIDE = "set_zone_override"

    # Entity services (DHW)
    SET_DHW_OVERRIDE = "set_dhw_override"
    CLEAR_DHW_OVERRIDE = "clear_dhw_override"
