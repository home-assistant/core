"""Data update coordinator for CityBikes."""

from __future__ import annotations

import logging
import sys
from datetime import timedelta

import aiohttp
from citybikes import __version__ as CITYBIKES_CLIENT_VERSION
from citybikes.asyncio import Client as CitybikesClient

from homeassistant.const import APPLICATION_NAME, __version__
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

HA_USER_AGENT = (
    f"{APPLICATION_NAME}/{__version__} "
    f"python-citybikes/{CITYBIKES_CLIENT_VERSION} "
    f"Python/{sys.version_info[0]}.{sys.version_info[1]}"
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
SCAN_INTERVAL = timedelta(minutes=5)


class CityBikesCoordinator(DataUpdateCoordinator):
    """Class to manage fetching CityBikes data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: CitybikesClient,
        network_id: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.network_id = network_id
        self.network = None

    async def _async_update_data(self):
        """Fetch data from CityBikes API."""
        try:
            network = await self.client.network(uid=self.network_id).fetch()
            self.network = network
            return {"stations": network.stations, "network": network}
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with CityBikes API: {err}") from err

