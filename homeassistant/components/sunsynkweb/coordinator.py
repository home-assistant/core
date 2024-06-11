"""Coordinator for the sunsynk web api."""

from __future__ import annotations

from asyncio import timeout as async_timeout
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pysunsynkweb.model import Installation, get_plants
from pysunsynkweb.session import SunsynkwebSession

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import SunsynkConfigEntry


class SunsynkUpdateCoordinator(DataUpdateCoordinator[None]):
    """A Coordinator that updates sunsynk plants."""

    config_entry: SunsynkConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="SunsynkPlantPolling",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.session = SunsynkwebSession(
            session=async_get_clientsession(hass),
            username=self.config_entry.data["username"],
            password=self.config_entry.data["password"],
        )
        self.cache = Installation([])

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        if not self.cache.plants:
            async with async_timeout(10):
                try:
                    self.cache = await get_plants(self.session)
                except KeyError as err:
                    raise UpdateFailed(
                        f"Error initialising communication with the sunsynk API: {err}"
                    ) from err
        try:
            await self.cache.update()
        except KeyError as err:
            raise UpdateFailed(f"Error updating from the sunsynk API: {err}") from err
