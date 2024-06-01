"""Coordinator for the sunsynk web api."""

from asyncio import timeout as async_timeout
from datetime import timedelta
import logging

from pysunsynkweb.model import get_plants
from pysunsynkweb.session import SunsynkwebSession

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class PlantUpdateCoordinator(DataUpdateCoordinator):
    """A Coordinator that updates sunsynk plants."""

    def __init__(self, hass: HomeAssistant, config) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="SunsynkPlantPolling",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.bearer = None
        self.config = config
        self.hass = hass
        self.session = SunsynkwebSession(
            session=async_get_clientsession(hass),
            username=config.data["username"],
            password=config.data["password"],
        )
        self.cache = None

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            if self.cache is None:
                async with async_timeout(10):
                    self.cache = await get_plants(self.session)
            await self.cache.update()
        except KeyError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
