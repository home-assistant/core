"""Services for the OpenWeatherMap integration."""

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import service

from .const import DOMAIN

SERVICE_GET_MINUTE_FORECAST = "get_minute_forecast"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the OpenWeatherMap integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_MINUTE_FORECAST,
        entity_domain=WEATHER_DOMAIN,
        schema=None,
        func="async_get_minute_forecast",
        supports_response=SupportsResponse.ONLY,
    )
