"""Define services for the Environment Canada integration."""

from enum import StrEnum
from typing import Any

from env_canada import ECPrecipForecast, ECWeather
import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import (
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CommonServiceArgument,
)
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class EnvironmentCanadaService(StrEnum):
    """Store keys for Environment Canada services."""

    GET_ALERTS = "get_alerts"
    GET_FORECASTS = "get_forecasts"
    GET_PRECIPITATION_FORECAST = "get_precipitation_forecast"
    SET_RADAR_TYPE = "set_radar_type"


class EnvironmentCanadaServiceArgument(StrEnum):
    """Store keys for Environment Canada service arguments."""

    PRECIP_TYPE = "precip_type"
    PAST_MINUTES = "past_minutes"
    FUTURE_MINUTES = "future_minutes"
    HOURLY_HOURS = "hourly_hours"
    RADAR_TYPE = "radar_type"


SET_RADAR_TYPE_SCHEMA: VolDictType = {
    probatio.Required(EnvironmentCanadaServiceArgument.RADAR_TYPE): probatio.In(
        ["Auto", "Rain", "Snow", "Precipitation type"]
    ),
}

SERVICE_GET_ALERTS_SCHEMA = probatio.Schema(
    {probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string}
)

SERVICE_GET_PRECIPITATION_FORECAST_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
        probatio.Optional(EnvironmentCanadaServiceArgument.PRECIP_TYPE): probatio.In(
            ["auto", "rain", "snow"]
        ),
        probatio.Optional(EnvironmentCanadaServiceArgument.PAST_MINUTES): probatio.All(
            int, probatio.Range(0, 180)
        ),
        probatio.Optional(
            EnvironmentCanadaServiceArgument.FUTURE_MINUTES
        ): probatio.All(int, probatio.Range(0, 72)),
        probatio.Optional(EnvironmentCanadaServiceArgument.HOURLY_HOURS): probatio.All(
            int, probatio.Range(0, 48)
        ),
    }
)

SNAKE_MAPPING = {
    "alertColourLevel": "alert_colour_level",
    "expiryTime": "expiry_time",
}

PRECIP_FORECAST_OPTIONS = (
    EnvironmentCanadaServiceArgument.PRECIP_TYPE,
    EnvironmentCanadaServiceArgument.PAST_MINUTES,
    EnvironmentCanadaServiceArgument.FUTURE_MINUTES,
    EnvironmentCanadaServiceArgument.HOURLY_HOURS,
)


async def _async_get_alerts(call: ServiceCall) -> dict[str, Any]:
    """Return the active alerts."""
    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
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
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
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
        EnvironmentCanadaService.GET_ALERTS,
        _async_get_alerts,
        schema=SERVICE_GET_ALERTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        EnvironmentCanadaService.GET_PRECIPITATION_FORECAST,
        _async_get_precipitation_forecast,
        schema=SERVICE_GET_PRECIPITATION_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        EnvironmentCanadaService.SET_RADAR_TYPE,
        entity_domain=CAMERA_DOMAIN,
        func="async_set_radar_type",
        schema=SET_RADAR_TYPE_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        EnvironmentCanadaService.GET_FORECASTS,
        entity_domain=WEATHER_DOMAIN,
        func="_async_environment_canada_forecasts",
        schema=None,
        supports_response=SupportsResponse.ONLY,
    )
