"""Define services for the Environment Canada integration."""

from typing import Any

from env_canada import ECPrecipForecast, ECWeather
import probatio

from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_GET_ALERTS = "get_alerts"
SERVICE_GET_ALERTS_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string}
)

SERVICE_GET_PRECIPITATION_FORECAST = "get_precipitation_forecast"
SERVICE_GET_PRECIPITATION_FORECAST_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Optional("precip_type"): probatio.In(["auto", "rain", "snow"]),
        probatio.Optional("past_minutes"): probatio.All(int, probatio.Range(0, 180)),
        probatio.Optional("future_minutes"): probatio.All(int, probatio.Range(0, 72)),
        probatio.Optional("hourly_hours"): probatio.All(int, probatio.Range(0, 48)),
    }
)

SNAKE_MAPPING = {
    "alertColourLevel": "alert_colour_level",
    "expiryTime": "expiry_time",
}

PRECIP_FORECAST_OPTIONS = (
    "precip_type",
    "past_minutes",
    "future_minutes",
    "hourly_hours",
)


async def _async_get_alerts(call: ServiceCall) -> dict[str, Any]:
    """Return the active alerts."""
    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    ec: ECWeather | None = entry.runtime_data.weather_coordinator.ec_data
    if ec is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_connected",
        )

    data: dict[str, Any] = ec.alerts
    return {
        k: [
            {SNAKE_MAPPING.get(ik, ik): iv for ik, iv in item.items()}
            for item in v["value"]
        ]
        for k, v in data.items()
    }


async def _async_get_precipitation_forecast(call: ServiceCall) -> dict[str, Any]:
    """Return the precipitation forecast series."""
    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    # A fresh object per call, rather than one shared across calls: its
    # options would otherwise leak between calls that omit them, and
    # concurrent calls could race on the same instance's attributes.
    kwargs: dict[str, Any] = {
        "coordinates": (entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE]),
        "language": entry.data.get(CONF_LANGUAGE, "English").lower(),
    }
    for option in PRECIP_FORECAST_OPTIONS:
        if option in call.data:
            kwargs[option] = call.data[option]

    precip = ECPrecipForecast(**kwargs)
    await precip.update()

    return {
        "nowcast": [
            {**item, "timestamp": item["timestamp"].isoformat()}
            for item in precip.nowcast
        ],
        "hourly": [
            {**item, "timestamp": item["timestamp"].isoformat()}
            for item in precip.hourly
        ],
        "metadata": precip.metadata,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Environment Canada integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ALERTS,
        _async_get_alerts,
        schema=SERVICE_GET_ALERTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRECIPITATION_FORECAST,
        _async_get_precipitation_forecast,
        schema=SERVICE_GET_PRECIPITATION_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
