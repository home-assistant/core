"""Services for the Victron Remote Monitoring integration."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import cast

import probatio
from victron_vrm.models.aggregations import ForecastAggregations

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


def _forecast_hours(
    solar: ForecastAggregations | None,
    consumption: ForecastAggregations | None,
    start: datetime | None,
    end: datetime | None,
) -> list[dict[str, JsonValueType]]:
    """Return hourly watt-hours inside the half-open window.

    Local ISO offsets stay distinct when a civil hour repeats.
    """
    time_zone = dt_util.DEFAULT_TIME_ZONE
    hours: dict[datetime, dict[str, float]] = {}
    for key, aggregation in (("solar", solar), ("consumption", consumption)):
        if aggregation is None:
            continue
        for unix_seconds, watt_hours in aggregation.records:
            instant = datetime.fromtimestamp(unix_seconds, UTC)
            if start is not None and instant < start:
                continue
            if end is not None and instant >= end:
                continue
            hours.setdefault(instant, {})[key] = watt_hours

    forecast: list[dict[str, JsonValueType]] = []
    for instant in sorted(hours):
        point: dict[str, JsonValueType] = {
            "datetime": instant.astimezone(time_zone).isoformat(),
            **hours[instant],
        }
        forecast.append(point)
    return forecast


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
            start = dt_util.as_utc(start)
        if end is not None:
            end = dt_util.as_utc(end)
        if start is not None and end is not None and end < start:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="end_before_start",
            )
        return {
            "forecast": cast(
                list[JsonValueType],
                _forecast_hours(store.solar, store.consumption, start, end),
            ),
        }

    hass.services.async_register(
        DOMAIN,
        VictronRemoteMonitoringService.GET_FORECAST,
        async_get_forecast,
        schema=GET_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
