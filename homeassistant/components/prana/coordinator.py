"""Coordinator for Prana integration.

Responsible for polling the device REST endpoints and normalizing data for entities.
"""

from datetime import timedelta
import logging

from prana_local_api_client.exceptions import (
    PranaApiCommunicationError,
    PranaApiUpdateFailed,
)
from prana_local_api_client.models.prana_device_info import PranaDeviceInfo
from prana_local_api_client.models.prana_state import PranaState
from prana_local_api_client.prana_api_client import PranaLocalApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=10)
COORDINATOR_NAME = f"{DOMAIN} coordinator"

type PranaConfigEntry = ConfigEntry[PranaCoordinator]


class PranaCoordinator(DataUpdateCoordinator[PranaState]):
    """Universal coordinator for Prana (fan, switch, sensor, light data)."""

    config_entry: PranaConfigEntry
    device_info: PranaDeviceInfo

    def __init__(self, hass: HomeAssistant, entry: PranaConfigEntry) -> None:
        """Initialize the Prana data update coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=COORDINATOR_NAME,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

        self.api_client = PranaLocalApiClient(host=entry.data[CONF_HOST], port=80)

    async def _async_setup(self) -> None:
        try:
            self.device_info = await self.api_client.get_device_info()
        except PranaApiCommunicationError as err:
            raise ConfigEntryNotReady("Could not fetch device info") from err

    async def _async_update_data(self) -> PranaState:
        """Fetch and normalize device state for all platforms."""
        try:
            state = await self.api_client.get_state()
        except PranaApiUpdateFailed as err:
            raise UpdateFailed(f"HTTP error communicating with device: {err}") from err
        except PranaApiCommunicationError as err:
            raise UpdateFailed(
                f"Network error communicating with device: {err}"
            ) from err
        return state
