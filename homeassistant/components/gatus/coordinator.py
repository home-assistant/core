"""DataUpdateCoordinator for the Gatus integration."""

from datetime import timedelta
import logging
from typing import Any, override

from gatus_api.client import GatusClient, GatusClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)

type GatusConfigEntry = ConfigEntry[GatusDataUpdateCoordinator]


class GatusDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching Gatus data from the API via third-party library."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, url: str) -> None:
        """Initialize the coordinator."""
        self.url = url.rstrip("/")
        self.client = GatusClient(url=self.url, session=async_get_clientsession(hass))

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @override
    async def _async_update_data(self):
        try:
            return await self.client.get_endpoints_statuses()
        except GatusClientError as err:
            raise UpdateFailed(f"Error communicating with Gatus API: {err}") from err
