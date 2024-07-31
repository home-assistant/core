"""Update coordinator for IronOS Integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiogithubapi import GitHubAPI
from pynecil import CommunicationError, DeviceInfoResponse, LiveDataResponse, Pynecil

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


class IronOSCoordinator(DataUpdateCoordinator[LiveDataResponse]):
    """IronOS coordinator."""

    device_info: DeviceInfoResponse
    config_entry: ConfigEntry
    latest_release: Any

    def __init__(self, hass: HomeAssistant, device: Pynecil) -> None:
        """Initialize IronOS coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    async def _async_update_data(self) -> LiveDataResponse:
        """Fetch data from Device."""

        try:
            await self.get_latest_release()
            return await self.device.get_live_data()

        except CommunicationError as e:
            raise UpdateFailed("Cannot connect to device") from e

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        try:
            self.device_info = await self.device.get_device_info()

        except CommunicationError as e:
            raise UpdateFailed("Cannot connect to device") from e
        await self.get_latest_release(no_throttle=True)

    @Throttle(timedelta(hours=1))
    async def get_latest_release(self) -> None:
        """Get latest release from github."""

        session = async_get_clientsession(self.hass)
        async with GitHubAPI(session=session) as github:
            self.latest_release = (
                await github.repos.releases.latest("Ralim/IronOS")
            ).data
