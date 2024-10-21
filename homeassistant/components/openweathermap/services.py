"""Services for OpenWeatherMap."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from . import WeatherUpdateCoordinator
from .const import ATTR_API_MINUTE_FORECAST, DOMAIN, OWM_MODE_V30

SERVICE_GET_MINUTE_FORECAST = f"get_{ATTR_API_MINUTE_FORECAST}"


async def async_setup_services(
    hass: HomeAssistant,
    mode: str,
    weather_coordinator: WeatherUpdateCoordinator,
) -> None:
    """Set up OpenWeatherMap services."""

    def handle_get_minute_forecasts(call: ServiceCall) -> None:
        """Handle the service action call."""
        return weather_coordinator.data[ATTR_API_MINUTE_FORECAST]

    if mode == OWM_MODE_V30:
        hass.services.async_register(
            domain=DOMAIN,
            service=SERVICE_GET_MINUTE_FORECAST,
            service_func=handle_get_minute_forecasts,
            supports_response=SupportsResponse.ONLY,
        )
    else:
        hass.services.async_remove(
            domain=DOMAIN,
            service=SERVICE_GET_MINUTE_FORECAST,
        )
