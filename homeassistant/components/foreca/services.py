"""Actions for the Foreca integration."""

from enum import StrEnum

import probatio

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN


class ForecaService(StrEnum):
    """Foreca actions."""

    GET_FORECASTS_EXTRA = "get_forecasts_extra"


class ForecaServiceArgument(StrEnum):
    """Foreca action fields."""

    TYPE = "type"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Foreca actions."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ForecaService.GET_FORECASTS_EXTRA,
        entity_domain=WEATHER_DOMAIN,
        schema={
            probatio.Required(ForecaServiceArgument.TYPE): probatio.In(
                ["daily", "hourly"]
            )
        },
        func="async_get_forecasts_extra",
        supports_response=SupportsResponse.ONLY,
    )
