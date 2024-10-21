"""Services for OpenWeatherMap."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from . import WeatherUpdateCoordinator
from .const import ATTR_API_MINUTE_FORECAST, DEFAULT_NAME, DOMAIN, OWM_MODE_V30

SERVICE_GET_MINUTE_FORECAST = f"get_{ATTR_API_MINUTE_FORECAST}"


async def async_setup_services(
    hass: HomeAssistant,
    mode: str,
    weather_coordinator: WeatherUpdateCoordinator,
) -> None:
    """Set up OpenWeatherMap services."""

    def handle_get_minute_forecasts(call: ServiceCall) -> None:
        """Handle the service action call."""
        if mode == OWM_MODE_V30:
            return weather_coordinator.data[ATTR_API_MINUTE_FORECAST]
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_minute_forecast_mode",
            translation_placeholders={"name": DEFAULT_NAME},
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_GET_MINUTE_FORECAST,
        service_func=handle_get_minute_forecasts,
        supports_response=SupportsResponse.ONLY,
    )
