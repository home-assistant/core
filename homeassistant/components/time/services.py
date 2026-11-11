"""Services for the Time integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DATA_COMPONENT, TimeService, TimeServiceArgument

if TYPE_CHECKING:
    from .entity import TimeEntity


async def _async_set_value(entity: TimeEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to set a new date."""
    return await entity.async_set_value(service_call.data[TimeServiceArgument.TIME])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the time services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        TimeService.SET_VALUE,
        {probatio.Required(TimeServiceArgument.TIME): cv.time},
        _async_set_value,
    )
