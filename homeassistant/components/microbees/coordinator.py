"""The microBees Coordinator."""

import asyncio
from datetime import timedelta
import logging

import aiohttp
from microBeesPy.microbees import MicroBees, MicroBeesException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class MicroBeesUpdateCoordinator(DataUpdateCoordinator):
    """MicroBees coordinator."""

    def __init__(self, hass: HomeAssistant, microbees: MicroBees) -> None:
        """Initialize microBees coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="microBees Coordinator",
            update_interval=timedelta(seconds=30),
        )
        self.microbees = microbees

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(10):
                bees = await self.microbees.getBees()
                data = {}
                for bee in bees:
                    data[f"bee_{bee.id}"] = bee
                    for act in bee.actuators:
                        data[f"act_{act.id}"] = act
                return data
        except aiohttp.ClientResponseError as err:
            raise ConfigEntryAuthFailed from err
        except MicroBeesException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
