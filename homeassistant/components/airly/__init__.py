"""The Airly integration."""
import asyncio
from datetime import timedelta
import logging
from math import floor

from aiohttp.client_exceptions import ClientConnectorError
from airly import Airly
from airly.exceptions import AirlyError
import async_timeout

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_API_ADVICE,
    ATTR_API_CAQI,
    ATTR_API_CAQI_DESCRIPTION,
    ATTR_API_CAQI_LEVEL,
    CONF_USE_NEAREST,
    DOMAIN,
    MINIMUM_UPDATE_INTERVAL,
    NO_AIRLY_SENSORS,
)

PLATFORMS = ["air_quality", "sensor"]

_LOGGER = logging.getLogger(__name__)


def set_update_interval(hass, instances, requests_remaining):
    """Set update_interval to all configured Airly instances."""
    if requests_remaining == 0:
        return

    # We check how many Airly configured instances are and calculate interval to not
    # exceed allowed numbers of requests. The number of requests is reset at midnight
    # UTC.
    now = dt_util.utcnow()
    midnight = dt_util.find_next_time_expression_time(
        now, seconds=[0], minutes=[0], hours=[0]
    )
    minutes_to_midnight = (midnight - now).seconds / 60

    interval = timedelta(
        max(minutes=floor(minutes_to_midnight / requests_remaining * instances)),
        MINIMUM_UPDATE_INTERVAL,
    )

    _LOGGER.debug("Data will be update every %s", interval)

    if hass.data.get(DOMAIN):
        for instance in hass.data[DOMAIN].values():
            instance.update_interval = interval


async def async_setup_entry(hass, config_entry):
    """Set up Airly as config entry."""
    api_key = config_entry.data[CONF_API_KEY]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    use_nearest = config_entry.data.get(CONF_USE_NEAREST, False)

    # For backwards compat, set unique ID
    if config_entry.unique_id is None:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=f"{latitude}-{longitude}"
        )

    websession = async_get_clientsession(hass)

    update_interval = timedelta(minutes=MINIMUM_UPDATE_INTERVAL)

    coordinator = AirlyDataUpdateCoordinator(
        hass, websession, api_key, latitude, longitude, update_interval, use_nearest
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class AirlyDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Airly data."""

    def __init__(
        self,
        hass,
        session,
        api_key,
        latitude,
        longitude,
        update_interval,
        use_nearest,
    ):
        """Initialize."""
        self.latitude = latitude
        self.longitude = longitude
        self.airly = Airly(api_key, session)
        self.use_nearest = use_nearest

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        """Update data via library."""
        data = {}
        if self.use_nearest:
            measurements = self.airly.create_measurements_session_nearest(
                self.latitude, self.longitude, max_distance_km=5
            )
        else:
            measurements = self.airly.create_measurements_session_point(
                self.latitude, self.longitude
            )
        with async_timeout.timeout(20):
            try:
                await measurements.update()
            except (AirlyError, ClientConnectorError) as error:
                raise UpdateFailed(error) from error

        _LOGGER.debug(
            "Requests remaining: %s/%s",
            self.airly.requests_remaining,
            self.airly.requests_per_day,
        )

        # Airly API sometimes returns None for requests remaining
        if self.airly.requests_remaining:
            set_update_interval(
                self.hass,
                len(self.hass.config_entries.async_entries(DOMAIN)),
                self.airly.requests_remaining,
            )

        values = measurements.current["values"]
        index = measurements.current["indexes"][0]
        standards = measurements.current["standards"]

        if index["description"] == NO_AIRLY_SENSORS:
            raise UpdateFailed("Can't retrieve data: no Airly sensors in this area")
        for value in values:
            data[value["name"]] = value["value"]
        for standard in standards:
            data[f"{standard['pollutant']}_LIMIT"] = standard["limit"]
            data[f"{standard['pollutant']}_PERCENT"] = standard["percent"]
        data[ATTR_API_CAQI] = index["value"]
        data[ATTR_API_CAQI_LEVEL] = index["level"].lower().replace("_", " ")
        data[ATTR_API_CAQI_DESCRIPTION] = index["description"]
        data[ATTR_API_ADVICE] = index["advice"]
        return data
