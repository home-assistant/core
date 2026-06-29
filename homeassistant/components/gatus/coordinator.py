"""DataUpdateCoordinator for the Gatus integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Any, override

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GatusDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching Gatus data from the API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, url: str) -> None:
        """Initialize the coordinator."""
        self.url = url.rstrip("/")
        self.session = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @override
    async def _async_update_data(self) -> list[dict]:
        """Fetch data from Gatus API endpoint."""
        try:
            async with asyncio.timeout(10):
                api_url = f"{self.url}/api/v1/endpoints/statuses"
                async with self.session.get(api_url) as response:
                    if response.status != 200:
                        raise UpdateFailed(
                            f"Gatus API returned status code {response.status}"
                        )

                    data = await response.json()
                    if not isinstance(data, list):
                        raise UpdateFailed(
                            "Gatus API response was not in the expected array format"
                        )
                    return data

        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with Gatus API: {err}") from err
