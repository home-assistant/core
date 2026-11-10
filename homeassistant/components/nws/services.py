"""Services for the National Weather Service (NWS) integration."""

from enum import StrEnum

import probatio

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN


class NWSService(StrEnum):
    """Store keys for National Weather Service (NWS) services."""

    GET_FORECASTS_EXTRA = "get_forecasts_extra"


class NWSServiceArgument(StrEnum):
    """Store keys for National Weather Service (NWS) service arguments."""

    TYPE = "type"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the National Weather Service (NWS) integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NWSService.GET_FORECASTS_EXTRA,
        entity_domain=WEATHER_DOMAIN,
        schema={
            probatio.Required(NWSServiceArgument.TYPE): probatio.In(
                ("hourly", "twice_daily")
            )
        },
        func="async_get_forecasts_extra_service",
        supports_response=SupportsResponse.ONLY,
    )
