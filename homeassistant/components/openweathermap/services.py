"""Services for OpenWeatherMap."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from . import WeatherUpdateCoordinator
from .const import ATTR_API_MINUTELY_FORECAST, DOMAIN

SERVICE_GET_MINUTELY_FORECAST = f"get_{ATTR_API_MINUTELY_FORECAST}"


async def async_setup_services(
    hass: HomeAssistant, weather_coordinator: WeatherUpdateCoordinator
) -> None:
    """Set up OpenWeatherMap services."""

    def handle_get_minutely_forecast(call: ServiceCall) -> None:
        """Handle the service action call."""
        return weather_coordinator.data[ATTR_API_MINUTELY_FORECAST]

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_GET_MINUTELY_FORECAST,
        service_func=handle_get_minutely_forecast,
        supports_response=SupportsResponse.ONLY,
    )
