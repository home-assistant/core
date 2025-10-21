"""Shared utilities for different supported platforms."""

from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
from buienradar.buienradar import parse_data
from buienradar.constants import (
    ATTRIBUTION,
    CONDITION,
    CONTENT,
    DATA,
    FEELTEMPERATURE,
    FORECAST,
    HUMIDITY,
    MESSAGE,
    PRESSURE,
    STATIONNAME,
    STATUS_CODE,
    SUCCESS,
    TEMPERATURE,
    VISIBILITY,
    WINDAZIMUTH,
    WINDGUST,
    WINDSPEED,
)
from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import DEFAULT_TIMEOUT, SCHEDULE_NOK, SCHEDULE_OK

__all__ = ["BrData"]
_LOGGER = logging.getLogger(__name__)

"""
Log at WARN level after WARN_THRESHOLD failures, otherwise log at
DEBUG level.
"""
WARN_THRESHOLD = 4


def threshold_log(count: int, *args, **kwargs) -> None:
    """Log at warn level after WARN_THRESHOLD failures, debug otherwise."""
    if count >= WARN_THRESHOLD:
        _LOGGER.warning(*args, **kwargs)
    else:
        _LOGGER.debug(*args, **kwargs)


class BrData:
    """Get the latest data and updates the states."""

    # Initialize to warn immediately if the first call fails.
    load_error_count: int = WARN_THRESHOLD
    rain_error_count: int = WARN_THRESHOLD

    def __init__(self, hass: HomeAssistant, coordinates, timeframe, devices) -> None:
        """Initialize the data object."""
        self.devices = devices
        self.data: dict[str, Any] | None = {}
        self.hass = hass
        self.coordinates = coordinates
        self.timeframe = timeframe
        self.unsub_schedule_update: CALLBACK_TYPE | None = None

    async def update_devices(self):
        """Update all devices/sensors."""
        if not self.devices:
            return

        # Update all devices
        for dev in self.devices:
            dev.data_updated(self)

    @callback
    def async_schedule_update(self, minute=1):
        """Schedule an update after minute minutes."""
        _LOGGER.debug("Scheduling next update in %s minutes", minute)
        nxt = dt_util.utcnow() + timedelta(minutes=minute)
        self.unsub_schedule_update = async_track_point_in_utc_time(
            self.hass, self.async_update, nxt
        )

    async def get_data(self, url):
        """Load data from specified url."""
        _LOGGER.debug("Calling url: %s", url)
        result = {SUCCESS: False, MESSAGE: None}
        resp = None
        try:
            websession = async_get_clientsession(self.hass)
            async with websession.get(
                url, timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            ) as resp:
                result[STATUS_CODE] = resp.status
                result[CONTENT] = await resp.text()
                if resp.status == HTTPStatus.OK:
                    result[SUCCESS] = True
                else:
                    result[MESSAGE] = f"Got http statuscode: {resp.status}"

                return result
        except (TimeoutError, aiohttp.ClientError) as err:
            result[MESSAGE] = str(err)
            return result
        finally:
            if resp is not None:
                resp.release()

    async def _async_update(self):
        """Update the data from buienradar."""
        content = await self.get_data(JSON_FEED_URL)

        if content.get(SUCCESS) is not True:
            # unable to get the data
            self.load_error_count += 1
            threshold_log(
                self.load_error_count,
                "Unable to retrieve json data from Buienradar (Msg: %s, status: %s)",
                content.get(MESSAGE),
                content.get(STATUS_CODE),
            )
            return None
        self.load_error_count = 0

        # rounding coordinates prevents unnecessary redirects/calls
        lat = self.coordinates[CONF_LATITUDE]
        lon = self.coordinates[CONF_LONGITUDE]
        rainurl = json_precipitation_forecast_url(lat, lon)
        raincontent = await self.get_data(rainurl)

        if raincontent.get(SUCCESS) is not True:
            self.rain_error_count += 1
            # unable to get the data
            threshold_log(
                self.rain_error_count,
                "Unable to retrieve rain data from Buienradar (Msg: %s, status: %s)",
                raincontent.get(MESSAGE),
                raincontent.get(STATUS_CODE),
            )
            return None
        self.rain_error_count = 0

        result = parse_data(
            content.get(CONTENT),
            raincontent.get(CONTENT),
            self.coordinates[CONF_LATITUDE],
            self.coordinates[CONF_LONGITUDE],
            self.timeframe,
            False,
        )

        _LOGGER.debug("Buienradar parsed data: %s", result)
        if result.get(SUCCESS) is not True:
            if int(datetime.now().strftime("%H")) > 0:
                _LOGGER.warning(
                    "Unable to parse data from Buienradar. (Msg: %s)",
                    result.get(MESSAGE),
                )
            return None

        return result[DATA]

    async def async_update(self, *_):
        """Update the data from buienradar and schedule the next update."""
        data = await self._async_update()

        if data is None:
            self.async_schedule_update(SCHEDULE_NOK)
            return

        self.data = data
        await self.update_devices()
        self.async_schedule_update(SCHEDULE_OK)

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
        except (ValueError, TypeError):
            return None

    @property
    def feeltemperature(self):
        """Return the feeltemperature, or None."""
        try:
            return float(self.data.get(FEELTEMPERATURE))
        except (ValueError, TypeError):
            return None

    @property
    def pressure(self):
        """Return the pressure, or None."""
        try:
            return float(self.data.get(PRESSURE))
        except (ValueError, TypeError):
            return None

    @property
    def humidity(self):
        """Return the humidity, or None."""
        try:
            return int(self.data.get(HUMIDITY))
        except (ValueError, TypeError):
            return None

    @property
    def visibility(self):
        """Return the visibility, or None."""
        try:
            return int(self.data.get(VISIBILITY))
        except (ValueError, TypeError):
            return None

    @property
    def wind_gust(self):
        """Return the windgust, or None."""
        try:
            return float(self.data.get(WINDGUST))
        except (ValueError, TypeError):
            return None

    @property
    def wind_speed(self):
        """Return the windspeed, or None."""
        try:
            return float(self.data.get(WINDSPEED))
        except (ValueError, TypeError):
            return None

    @property
    def wind_bearing(self):
        """Return the wind bearing, or None."""
        try:
            return int(self.data.get(WINDAZIMUTH))
        except (ValueError, TypeError):
            return None

    @property
    def forecast(self):
        """Return the forecast data."""
        return self.data.get(FORECAST)
