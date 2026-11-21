"""Services for the IRM KMI integration."""

from enum import StrEnum

import probatio

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class IrmKmiService(StrEnum):
    """Store keys for IRM KMI services."""

    GET_FORECASTS_RADAR = "get_forecasts_radar"


class IrmKmiServiceArgument(StrEnum):
    """Store keys for IRM KMI service arguments."""

    INCLUDE_PAST_FORECASTS = "include_past_forecasts"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the IRM KMI services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        IrmKmiService.GET_FORECASTS_RADAR,
        entity_domain=WEATHER_DOMAIN,
        schema={
            probatio.Optional(
                IrmKmiServiceArgument.INCLUDE_PAST_FORECASTS, default=False
            ): cv.boolean
        },
        func="async_get_forecasts_radar",
        supports_response=SupportsResponse.ONLY,
    )
