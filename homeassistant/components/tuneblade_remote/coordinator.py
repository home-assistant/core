"""Integration to integrate TuneBlade Remote devices with Home Assistant."""

from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError
from pytuneblade import TuneBladeApiClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TuneBladeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator to fetch data from the TuneBlade hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TuneBladeApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self.data: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch the latest data from TuneBlade."""
        try:
            devices_data = await self.client.async_get_data()
            if not devices_data:
                raise UpdateFailed("No device data returned from TuneBlade hub.")
        except ClientError as err:
            _LOGGER.warning("Error fetching data from TuneBlade hub")
            raise UpdateFailed(
                f"Error communicating with TuneBlade hub: {err}"
            ) from err

        _LOGGER.debug("Fetched device data: %s", devices_data)
        return devices_data
