"""Services for the Date integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DATA_COMPONENT, DateService, DateServiceArgument

if TYPE_CHECKING:
    from .entity import DateEntity


async def _async_set_value(entity: DateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new date."""
    return await entity.async_set_value(service_call.data[DateServiceArgument.DATE])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the date services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        DateService.SET_VALUE,
        {probatio.Required(DateServiceArgument.DATE): cv.date},
        _async_set_value,
    )
