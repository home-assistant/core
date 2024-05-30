"""The constants of the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum, unique
from typing import Final

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

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

CONFIG_SCHEMA: Final = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT
                ): vol.All(cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

ATTR_SYSTEM_MODE: Final = "mode"
ATTR_DURATION_DAYS: Final = "period"
ATTR_DURATION_HOURS: Final = "duration"

ATTR_ZONE_TEMP: Final = "setpoint"
ATTR_DURATION_UNTIL: Final = "duration"


@unique
class EvoService(StrEnum):
    """The Evohome services."""

    REFRESH_SYSTEM: Final = "refresh_system"
    SET_SYSTEM_MODE: Final = "set_system_mode"
    RESET_SYSTEM: Final = "reset_system"
    SET_ZONE_OVERRIDE: Final = "set_zone_override"
    RESET_ZONE_OVERRIDE: Final = "clear_zone_override"


# system mode schemas are built dynamically when the services are regiatered


RESET_ZONE_OVERRIDE_SCHEMA: Final = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_id}
)
SET_ZONE_OVERRIDE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ZONE_TEMP): vol.All(
            vol.Coerce(float), vol.Range(min=4.0, max=35.0)
        ),
        vol.Optional(ATTR_DURATION_UNTIL): vol.All(
            cv.time_period, vol.Range(min=timedelta(days=0), max=timedelta(days=1))
        ),
    }
)
