"""Integration to integrate TuneBlade Remote devices with Home Assistant."""

from datetime import timedelta
import logging

from aiohttp import ClientError
from pytuneblade import TuneBladeApiClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)


class TuneBladeDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from the TuneBlade hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TuneBladeApiClient,
        scan_interval: timedelta = SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=scan_interval)
        self.client = client
        self.data = {}

    async def async_init(self) -> None:
        """Initialize the coordinator with first data fetch and error handling."""
        try:
            await self.async_config_entry_first_refresh()
        except (UpdateFailed, ClientError) as err:
            _LOGGER.error("Error connecting to TuneBlade hub: %s", err)
            raise ConfigEntryNotReady from err

    async def _async_update_data(self):
        """Fetch the latest data from TuneBlade."""
        try:
            devices_data = await self.client.async_get_data()
            if not devices_data:
                raise UpdateFailed("No device data returned from TuneBlade hub.")
        except ClientError as err:
            _LOGGER.exception("Error fetching data from TuneBlade hub")
            raise UpdateFailed(
                f"Error communicating with TuneBlade hub: {err}"
            ) from err

        _LOGGER.debug("Fetched device data: %s", devices_data)
        return devices_data
