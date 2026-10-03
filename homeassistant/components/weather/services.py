"""Services for the weather integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_COMPONENT, SERVICE_GET_FORECASTS, WeatherEntityFeature

if TYPE_CHECKING:
    from . import WeatherEntity


def raise_unsupported_forecast(entity_id: str, forecast_type: str) -> None:
    """Raise error on attempt to get an unsupported forecast."""
    raise HomeAssistantError(
        f"Weather entity '{entity_id}' does not support '{forecast_type}' forecast"
    )


async def _async_get_forecasts_service(
    weather: WeatherEntity, service_call: ServiceCall
) -> ServiceResponse:
    """Get weather forecast."""
    forecast_type = service_call.data["type"]
    supported_features = weather.supported_features or 0
    if forecast_type == "daily":
        if (supported_features & WeatherEntityFeature.FORECAST_DAILY) == 0:
            raise_unsupported_forecast(weather.entity_id, forecast_type)
        native_forecast_list = await weather.async_forecast_daily()
    elif forecast_type == "hourly":
        if (supported_features & WeatherEntityFeature.FORECAST_HOURLY) == 0:
            raise_unsupported_forecast(weather.entity_id, forecast_type)
        native_forecast_list = await weather.async_forecast_hourly()
    else:
        if (supported_features & WeatherEntityFeature.FORECAST_TWICE_DAILY) == 0:
            raise_unsupported_forecast(weather.entity_id, forecast_type)
        native_forecast_list = await weather.async_forecast_twice_daily()
    if native_forecast_list is None:
        converted_forecast_list = []
    else:
        converted_forecast_list = weather._convert_forecast(native_forecast_list)  # noqa: SLF001
    return {
        "forecast": converted_forecast_list,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the weather services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        SERVICE_GET_FORECASTS,
        {probatio.Required("type"): probatio.In(("daily", "hourly", "twice_daily"))},
        _async_get_forecasts_service,
        required_features=[
            WeatherEntityFeature.FORECAST_DAILY,
            WeatherEntityFeature.FORECAST_HOURLY,
            WeatherEntityFeature.FORECAST_TWICE_DAILY,
        ],
        supports_response=SupportsResponse.ONLY,
    )
