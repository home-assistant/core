"""The GIOS component."""
import asyncio
from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from gios import ApiError, Gios, NoStationError

from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import CONF_STATION_ID, DATA_CLIENT, DOMAIN

DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured GIOS."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    return True


async def async_setup_entry(hass, config_entry):
    """Set up GIOS as config entry."""
    station_id = config_entry.data[CONF_STATION_ID]
    _LOGGER.debug("Using station_id: %s", station_id)

    websession = async_get_clientsession(hass)

    gios = GiosData(websession, station_id)

    await gios.async_update()

    if not gios.available:
        raise ConfigEntryNotReady()

    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = gios

    config_entry.add_update_listener(update_listener)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "air_quality")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
    await hass.config_entries.async_forward_entry_unload(config_entry, "air_quality")
    return True


async def update_listener(hass, entry):
    """Update listener."""
    await hass.config_entries.async_forward_entry_unload(entry, "air_quality")
    hass.async_add_job(
        hass.config_entries.async_forward_entry_setup(entry, "air_quality")
    )


class GiosData:
    """Define an object to hold GIOS data."""

    def __init__(self, session, station_id):
        """Initialize."""
        self._gios = Gios(station_id, session)
        self.station_id = station_id
        self.sensors = {}
        self.latitude = None
        self.longitude = None
        self.station_name = None
        self.available = True

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_update(self):
        """Update GIOS data."""
        try:
            with timeout(30):
                await self._gios.update()
        except asyncio.TimeoutError:
            _LOGGER.error("Asyncio Timeout Error")
        except (ApiError, NoStationError, ClientConnectorError) as error:
            _LOGGER.error("GIOS data update failed: %s", error)
        self.available = self._gios.available
        self.latitude = self._gios.latitude
        self.longitude = self._gios.longitude
        self.station_name = self._gios.station_name
        self.sensors = self._gios.data
