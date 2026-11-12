"""Services for the bosch_alarm integration."""

import asyncio
import datetime as dt
from enum import StrEnum
from typing import Any

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .types import BoschAlarmConfigEntry


class BoschAlarmService(StrEnum):
    """Store keys for Bosch Alarm services."""

    SET_DATE_TIME = "set_date_time"


class BoschAlarmServiceArgument(StrEnum):
    """Store keys for Bosch Alarm service arguments."""

    DATETIME = "datetime"


def validate_datetime(value: Any) -> dt.datetime:
    """Validate that a provided datetime is supported on a bosch alarm panel."""
    date_val = cv.datetime(value)
    if date_val.year < 2010:
        raise probatio.RangeInvalid("datetime must be after 2009")

    if date_val.year > 2037:
        raise probatio.RangeInvalid("datetime must be before 2038")

    return date_val


SET_DATE_TIME_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(BoschAlarmServiceArgument.DATETIME): validate_datetime,
    }
)


async def async_set_panel_date(call: ServiceCall) -> None:
    """Set the date and time on a bosch alarm panel."""
    value: dt.datetime = call.data.get(
        BoschAlarmServiceArgument.DATETIME, dt_util.now()
    )
    config_entry: BoschAlarmConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    panel = config_entry.runtime_data
    try:
        await panel.set_panel_date(value)
    except asyncio.InvalidStateError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"target": config_entry.title},
        ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the bosch alarm integration."""

    hass.services.async_register(
        DOMAIN,
        BoschAlarmService.SET_DATE_TIME,
        async_set_panel_date,
        schema=SET_DATE_TIME_SCHEMA,
    )
