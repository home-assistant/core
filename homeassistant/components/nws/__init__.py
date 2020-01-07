"""The National Weather Service integration."""
import asyncio
import datetime
import logging

import aiohttp
from pynws import SimpleNWS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather"]

UPDATE_INTERVAL = datetime.timedelta(minutes=10)


def unique_id(latitude, longitude):
    """Return unique_id for entries."""
    return f"{latitude}_{longitude}"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the National Weather Service component."""
    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up National Weather Service from a config entry."""
    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
    station = entry.data.get(CONF_STATION)
    api_key = entry.data[CONF_API_KEY]

    client_session = async_get_clientsession(hass)

    nws_data = NwsData(hass, latitude, longitude, api_key, client_session)
    try:
        await nws_data.set_station(station)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.error("Error automatically setting station: %s", str(err))
        return False

    hass.data[DOMAIN][entry.entry_id] = nws_data

    await nws_data.update()
    async_track_time_interval(hass, nws_data.update, UPDATE_INTERVAL)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NwsData:
    """Data class for National Weather Service integration."""

    def __init__(self, hass, latitude, longitude, api_key, websession):
        """Initialize the data."""
        self.hass = hass
        self.latitude = latitude
        self.longitude = longitude
        ha_api_key = f"{api_key} homeassistant"
        self.nws = SimpleNWS(latitude, longitude, ha_api_key, websession)

    async def set_station(self, station):
        """
        Set to desired station.

        If None, nearest station is used.
        """
        await self.nws.set_station(station)

    @property
    def station(self):
        """Return station name."""
        return self.nws.station

    @property
    def observation(self):
        """Return observation."""
        return self.nws.observation

    @property
    def forecast(self):
        """Return day+night forecast."""
        return self.nws.forecast

    @property
    def forecast_hourly(self):
        """Return hourly forecast."""
        return self.nws.forecast_hourly

    async def update(self, now=None):
        """Update all data."""
        await self.nws.update_observation()
        await self.nws.update_forecast()
        await self.nws.update_forecast_hourly()
        async_dispatcher_send(self.hass, DOMAIN)
