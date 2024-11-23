"""Update coordinator for IronOS Integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiogithubapi import GitHubAPI, GitHubException, GitHubReleaseModel
from pynecil import CommunicationError, DeviceInfoResponse, LiveDataResponse, Pynecil

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
SCAN_INTERVAL_GITHUB = timedelta(hours=3)


class IronOSLiveDataCoordinator(DataUpdateCoordinator[LiveDataResponse]):
    """IronOS live data coordinator."""

    device_info: DeviceInfoResponse
    config_entry: ConfigEntry

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
            # device info is cached and won't be refetched on every
            # coordinator refresh, only after the device has disconnected
            # the device info is refetched
            self.device_info = await self.device.get_device_info()
            return await self.device.get_live_data()

        except CommunicationError as e:
            raise UpdateFailed("Cannot connect to device") from e


class IronOSFirmwareUpdateCoordinator(DataUpdateCoordinator[GitHubReleaseModel]):
    """IronOS coordinator for retrieving update information from github."""

    def __init__(self, hass: HomeAssistant, github: GitHubAPI) -> None:
        """Initialize IronOS coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL_GITHUB,
        )
        self.github = github

    async def _async_update_data(self) -> GitHubReleaseModel:
        """Fetch data from Github."""

        try:
            release = await self.github.repos.releases.latest("Ralim/IronOS")

        except GitHubException as e:
            raise UpdateFailed(
                "Failed to retrieve latest release data from Github"
            ) from e

        if TYPE_CHECKING:
            assert release.data

        return release.data
