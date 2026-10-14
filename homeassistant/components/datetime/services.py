"""Services for the Date/Time integration."""

from datetime import datetime
from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import ATTR_DATETIME, DATA_COMPONENT, SERVICE_SET_VALUE

if TYPE_CHECKING:
    from . import DateTimeEntity


async def _async_set_value(entity: DateTimeEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new date/time."""
    value: datetime = service_call.data[ATTR_DATETIME]
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    return await entity.async_set_value(value)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the date/time services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        SERVICE_SET_VALUE,
        {
            probatio.Required(ATTR_DATETIME): cv.datetime,
        },
        _async_set_value,
    )
