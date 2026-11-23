"""Services for the Honeywell Lyric integration."""

from enum import StrEnum
from time import localtime, strftime, time

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class LyricService(StrEnum):
    """Store keys for Honeywell Lyric services."""

    SET_HOLD_TIME = "set_hold_time"


class LyricServiceArgument(StrEnum):
    """Store keys for Honeywell Lyric service arguments."""

    TIME_PERIOD = "time_period"


SCHEMA_HOLD_TIME: VolDictType = {
    probatio.Required(
        LyricServiceArgument.TIME_PERIOD, default="01:00:00"
    ): probatio.All(
        cv.time_period,
        cv.positive_timedelta,
        lambda td: strftime("%H:%M:%S", localtime(time() + td.total_seconds())),
    )
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Honeywell Lyric integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        LyricService.SET_HOLD_TIME,
        entity_domain=CLIMATE_DOMAIN,
        schema=SCHEMA_HOLD_TIME,
        func="async_set_hold_time",
    )
