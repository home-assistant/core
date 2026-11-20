"""Shared utilities for different supported platforms."""

from http import HTTPStatus
import logging
from typing import Any

import aiohttp
from buienradar.buienradar import parse_data
from buienradar.constants import (
    ATTRIBUTION,
    CONDITION,
    DATA,
    FEELTEMPERATURE,
    FORECAST,
    HUMIDITY,
    MESSAGE,
    PRESSURE,
    STATIONNAME,
    SUCCESS,
    TEMPERATURE,
    VISIBILITY,
    WINDAZIMUTH,
    WINDGUST,
    WINDSPEED,
)
from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_TIMEOUT, SERVICE_TIME_ZONE

__all__ = ["BuienradarData", "async_fetch_data", "async_in_service_quiet_hour"]
_LOGGER = logging.getLogger(__name__)


async def async_in_service_quiet_hour() -> bool:
    """Return whether buienradar.nl is in its nightly forecast update hour.

    buienradar.nl updates its forecast for the next day between 00:00 and 01:00
    CE(S)T and often serves nothing during that hour. The hour that decides this
    is the one at the service, not in the user's configured time zone.
    """
    service_tz = await dt_util.async_get_time_zone(SERVICE_TIME_ZONE)
    return service_tz is not None and dt_util.utcnow().astimezone(service_tz).hour == 0


async def _async_get_content(hass: HomeAssistant, url: str, name: str) -> str:
    """Load the content of a Buienradar url."""
    _LOGGER.debug("Calling url: %s", url)
    websession = async_get_clientsession(hass)
    try:
        async with websession.get(
            url, timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
        ) as resp:
            content = await resp.text()
    except (TimeoutError, aiohttp.ClientError) as err:
        raise UpdateFailed(f"Unable to retrieve {name} from Buienradar: {err}") from err
    if resp.status != HTTPStatus.OK:
        raise UpdateFailed(
            f"Unable to retrieve {name} from Buienradar (status: {resp.status})"
        )
    return content


async def async_fetch_data(
    hass: HomeAssistant, coordinates: dict[str, float], timeframe: int
) -> dict[str, Any]:
    """Fetch and parse the Buienradar data for a location."""
    content = await _async_get_content(hass, JSON_FEED_URL, "json data")

    # rounding coordinates prevents unnecessary redirects/calls
    latitude = coordinates[CONF_LATITUDE]
    longitude = coordinates[CONF_LONGITUDE]
    raincontent = await _async_get_content(
        hass, json_precipitation_forecast_url(latitude, longitude), "rain data"
    )

    result = parse_data(content, raincontent, latitude, longitude, timeframe, False)
    _LOGGER.debug("Buienradar parsed data: %s", result)
    if result.get(SUCCESS) is not True:
        raise UpdateFailed(
            f"Unable to parse data from Buienradar. (Msg: {result.get(MESSAGE)})"
        )
    return result[DATA]


class BuienradarData:
    """Typed access to the parsed Buienradar data."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize with the parsed data."""
        self.data = data

    @property
    def attribution(self):
        """Return the attribution."""
        return self.data.get(ATTRIBUTION)

    @property
    def stationname(self):
        """Return the name of the selected weatherstation."""
        return self.data.get(STATIONNAME)

    @property
    def condition(self):
        """Return the condition."""
        return self.data.get(CONDITION)

    @property
    def temperature(self):
        """Return the temperature, or None."""
        try:
            return float(self.data.get(TEMPERATURE))
        except ValueError, TypeError:
            return None

    @property
    def feeltemperature(self):
        """Return the feeltemperature, or None."""
        try:
            return float(self.data.get(FEELTEMPERATURE))
        except ValueError, TypeError:
            return None

    @property
    def pressure(self):
        """Return the pressure, or None."""
        try:
            return float(self.data.get(PRESSURE))
        except ValueError, TypeError:
            return None

    @property
    def humidity(self):
        """Return the humidity, or None."""
        try:
            return int(self.data.get(HUMIDITY))
        except ValueError, TypeError:
            return None

    @property
    def visibility(self):
        """Return the visibility, or None."""
        try:
            return int(self.data.get(VISIBILITY))
        except ValueError, TypeError:
            return None

    @property
    def wind_gust(self):
        """Return the windgust, or None."""
        try:
            return float(self.data.get(WINDGUST))
        except ValueError, TypeError:
            return None

    @property
    def wind_speed(self):
        """Return the windspeed, or None."""
        try:
            return float(self.data.get(WINDSPEED))
        except ValueError, TypeError:
            return None

    @property
    def wind_bearing(self):
        """Return the wind bearing, or None."""
        try:
            return int(self.data.get(WINDAZIMUTH))
        except ValueError, TypeError:
            return None

    @property
    def forecast(self):
        """Return the forecast data."""
        return self.data.get(FORECAST)
