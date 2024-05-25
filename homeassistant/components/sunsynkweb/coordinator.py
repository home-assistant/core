"""Coordinator for the sunsynk web api."""

from asyncio import timeout as async_timeout
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import get_bearer_token
from .model import _LOGGER, get_plants


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
        self.session = async_get_clientsession(hass)
        self.cache = None

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout(10):
                if self.bearer is None:
                    self.bearer = await get_bearer_token(
                        self.session,
                        self.config.data["username"],
                        self.config.data["password"],
                    )
                if self.cache is None:
                    self.cache = await get_plants(self)
                await self.cache.update(self)
        except KeyError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
