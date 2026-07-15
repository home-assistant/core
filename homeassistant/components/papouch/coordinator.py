"""Data update coordinator for the Papouch integration."""

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .APIClient import PapouchApiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .devices import PapouchDevice

_LOGGER = logging.getLogger(__name__)


class PapouchDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Papouch data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: PapouchApiClient,
        entry: ConfigEntry,
        device: PapouchDevice,
    ) -> None:
        """Initialize the coordinator."""
        interval = entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self.api_client = api_client
        self.device = device

    async def _async_update_data(self) -> dict:
        """Fetch data from the device."""
        try:
            raw_xml = await self.api_client.fetch_data()
            return self.device.parse_xml(raw_xml)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from None
