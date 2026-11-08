"""Services for the Victron Remote Monitoring integration."""

from datetime import datetime
from enum import StrEnum

import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import DOMAIN
from .coordinator import VictronRemoteMonitoringConfigEntry


class VictronRemoteMonitoringService(StrEnum):
    """Store keys for Victron Remote Monitoring services."""

    GET_FORECAST = "get_forecast"


class VictronRemoteMonitoringServiceArgument(StrEnum):
    """Store keys for Victron Remote Monitoring service arguments."""

    CONFIG_ENTRY = "config_entry"
    START = "start"
    END = "end"


GET_FORECAST_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            VictronRemoteMonitoringServiceArgument.CONFIG_ENTRY
        ): ConfigEntrySelector({"integration": DOMAIN}),
        probatio.Optional(VictronRemoteMonitoringServiceArgument.START): cv.datetime,
        probatio.Optional(VictronRemoteMonitoringServiceArgument.END): cv.datetime,
    }
)


def _in_default_timezone(value: datetime) -> datetime:
    """Interpret a naive datetime in the Home Assistant default timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return value


def _series_response(
    points: dict[datetime, float],
    start: datetime | None,
    end: datetime | None,
) -> dict[str, JsonValueType]:
    """Return watt-hours keyed by ISO timestamps in the default timezone."""
    time_zone = dt_util.DEFAULT_TIME_ZONE
    response: dict[str, JsonValueType] = {}
    for timestamp in sorted(points):
        if start is not None and timestamp < start:
            continue
        if end is not None and timestamp >= end:
            break
        response[timestamp.astimezone(time_zone).isoformat()] = points[timestamp]
    return response


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Victron Remote Monitoring integration."""

    async def async_get_forecast(call: ServiceCall) -> ServiceResponse:
        """Return the cached hourly solar and consumption forecasts."""
        entry: VictronRemoteMonitoringConfigEntry = service.async_get_config_entry(
            hass,
            DOMAIN,
            call.data[VictronRemoteMonitoringServiceArgument.CONFIG_ENTRY],
        )
        store = entry.runtime_data.data
        start: datetime | None = call.data.get(
            VictronRemoteMonitoringServiceArgument.START
        )
        end: datetime | None = call.data.get(VictronRemoteMonitoringServiceArgument.END)
        if start is not None:
            start = _in_default_timezone(start)
        if end is not None:
            end = _in_default_timezone(end)
        if start is not None and end is not None and end < start:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="end_before_start",
            )
        return {
            "solar_wh": _series_response(store.solar_wh, start, end),
            "consumption_wh": _series_response(store.consumption_wh, start, end),
        }

    hass.services.async_register(
        DOMAIN,
        VictronRemoteMonitoringService.GET_FORECAST,
        async_get_forecast,
        schema=GET_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
