"""The GIOS component."""
import logging

from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from gios import ApiError, Gios, InvalidSensorsData, NoStationError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION_ID, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["air_quality"]


async def async_setup_entry(hass, entry):
    """Set up GIOS as config entry."""
    station_id = entry.data[CONF_STATION_ID]
    _LOGGER.debug("Using station_id: %s", station_id)

    websession = async_get_clientsession(hass)

    coordinator = GiosDataUpdateCoordinator(hass, websession, station_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class GiosDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold GIOS data."""

    def __init__(self, hass, session, station_id):
        """Class to manage fetching GIOS data API."""
        self.gios = Gios(station_id, session)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            with timeout(30):
                data = await self.gios.async_update()
        except (
            ApiError,
            NoStationError,
            ClientConnectorError,
            InvalidSensorsData,
        ) as error:
            raise UpdateFailed(error) from error
        return data
