"""The GIOS component."""
import logging

from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from gios import ApiError, Gios, InvalidSensorsData, NoStationError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION_ID, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry):
    """Set up GIOS as config entry."""
    station_id = config_entry.data[CONF_STATION_ID]
    _LOGGER.debug("Using station_id: %s", station_id)

    websession = async_get_clientsession(hass)

    coordinator = GiosDataUpdateCoordinator(hass, websession, station_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "air_quality")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(config_entry.entry_id)
    await hass.config_entries.async_forward_entry_unload(config_entry, "air_quality")
    return True


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
                await self.gios.update()
        except (
            ApiError,
            NoStationError,
            ClientConnectorError,
            InvalidSensorsData,
        ) as error:
            raise UpdateFailed(error) from error
        return self.gios.data
