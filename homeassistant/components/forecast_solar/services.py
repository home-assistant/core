"""Services for the Forecast.Solar integration."""

from datetime import datetime
from typing import TYPE_CHECKING

import voluptuous as vol

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

if TYPE_CHECKING:
    from .coordinator import ForecastSolarConfigEntry

ATTR_CONFIG_ENTRY = "config_entry"
ATTR_START = "start"
ATTR_END = "end"
ATTR_RESOLUTION = "resolution"

RESOLUTION_RAW = "raw"
RESOLUTION_HOURLY = "hourly"

SERVICE_GET_FORECAST = "get_forecast"

GET_FORECAST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_START): cv.datetime,
        vol.Optional(ATTR_END): cv.datetime,
        vol.Optional(ATTR_RESOLUTION, default=RESOLUTION_RAW): vol.In(
            (RESOLUTION_RAW, RESOLUTION_HOURLY)
        ),
    }
)


def _aggregate_hourly(
    watts: dict[datetime, int], wh_period: dict[datetime, int]
) -> tuple[dict[datetime, float], dict[datetime, int]]:
    """Aggregate raw forecast series to whole-hour resolution.

    The Forecast.Solar API returns timestamps at the boundary of each
    interval. We bucket each entry by its hour-floor, average the power
    values within the hour, and sum the energy values.
    """
    hourly_watts_buckets: dict[datetime, list[int]] = {}
    hourly_wh: dict[datetime, int] = {}

    for ts, w in watts.items():
        hour = ts.replace(minute=0, second=0, microsecond=0)
        hourly_watts_buckets.setdefault(hour, []).append(w)

    for ts, wh in wh_period.items():
        hour = ts.replace(minute=0, second=0, microsecond=0)
        hourly_wh[hour] = hourly_wh.get(hour, 0) + wh

    hourly_watts: dict[datetime, float] = {
        hour: sum(values) / len(values) for hour, values in hourly_watts_buckets.items()
    }
    return hourly_watts, hourly_wh


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Forecast.Solar integration."""

    async def async_get_forecast(call: ServiceCall) -> ServiceResponse:
        """Return the solar production forecast time series.

        The response has two flat ``{ISO timestamp -> number}`` maps,
        mirroring the today-attribute shape on the energy sensors:

        - ``watts``: estimated instantaneous power in W at the timestamp.
        - ``wh_period``: energy in Wh produced during the interval that
          starts at the timestamp.

        Timestamps are emitted in the site/API timezone (e.g.
        ``+10:00``), not UTC.
        """
        entry: ForecastSolarConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
        )
        estimate = entry.runtime_data.data

        wh_period: dict[datetime, int] = dict(estimate.wh_period)
        watts: dict[datetime, float]

        if call.data[ATTR_RESOLUTION] == RESOLUTION_HOURLY:
            watts, wh_period = _aggregate_hourly(dict(estimate.watts), wh_period)
        else:
            watts = dict(estimate.watts)

        start: datetime | None = call.data.get(ATTR_START)
        end: datetime | None = call.data.get(ATTR_END)

        # Interpret naive inputs in the forecast's zone; use the async
        # helper to avoid blocking tz-data I/O on first use.
        tz = (
            await dt_util.async_get_time_zone(estimate.timezone)
            if estimate.timezone
            else None
        )
        if start is not None and start.tzinfo is None:
            start = start.replace(tzinfo=tz)
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=tz)
        if start is not None and end is not None and end < start:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="end_before_start",
            )

        # Emit ISO keys in the site timezone so consumers see the local
        # offset (e.g. ``+10:00``).
        watts_out: dict[str, JsonValueType] = {}
        wh_out: dict[str, JsonValueType] = {}
        for ts in sorted(watts):
            if start is not None and ts < start:
                continue
            if end is not None and ts >= end:
                break
            local_iso = (ts.astimezone(tz) if tz is not None else ts).isoformat()
            watts_out[local_iso] = watts[ts]
            if ts in wh_period:
                wh_out[local_iso] = wh_period[ts]

        return {"watts": watts_out, "wh_period": wh_out}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_FORECAST,
        async_get_forecast,
        schema=GET_FORECAST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
