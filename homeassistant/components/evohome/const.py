"""The constants of the Evohome integration."""

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

SCAN_INTERVAL_DEFAULT: Final = timedelta(seconds=300)
SCAN_INTERVAL_MINIMUM: Final = timedelta(seconds=60)

# Schedules are weekly, so are re-fetched only to pick up any changes made elsewhere
SCHEDULE_MAX_AGE: Final = timedelta(hours=1)

NEXT_SP_FROM: Final = "next_sp_from"
THIS_SP_FROM: Final = "this_sp_from"


@unique
class EvoService(StrEnum):
    """The Evohome services."""

    SET_SYSTEM_MODE = "set_system_mode"
    SET_ZONE_OVERRIDE = "set_zone_override"
    SET_DHW_OVERRIDE = "set_dhw_override"


@unique
class EvoServiceArgument(StrEnum):
    """The Evohome service arguments."""

    MODE = "mode"
    PERIOD = "period"
    DURATION = "duration"
    SETPOINT = "setpoint"
    STATE = "state"
