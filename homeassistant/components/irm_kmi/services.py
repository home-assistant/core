"""Services for the IRM KMI integration."""

import probatio

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_INCLUDE_PAST_FORECASTS, DOMAIN, SERVICE_GET_FORECASTS_RADAR


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the IRM KMI services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_FORECASTS_RADAR,
        entity_domain=WEATHER_DOMAIN,
        schema={
            probatio.Optional(ATTR_INCLUDE_PAST_FORECASTS, default=False): cv.boolean
        },
        func="async_get_forecasts_radar",
        supports_response=SupportsResponse.ONLY,
    )
