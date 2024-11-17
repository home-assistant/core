"""Update coordinator for IronOS Integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiogithubapi import GitHubAPI, GitHubException, GitHubReleaseModel
from pynecil import CommunicationError, DeviceInfoResponse, LiveDataResponse, Pynecil

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SERIAL_NUMBER, CONF_SW_VERSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
SCAN_INTERVAL_GITHUB = timedelta(hours=3)


class IronOSLiveDataCoordinator(DataUpdateCoordinator[LiveDataResponse]):
    """IronOS live data coordinator."""

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
        self.device_info = DeviceInfoResponse()
        self.data = LiveDataResponse()

    async def _async_update_data(self) -> LiveDataResponse:
        """Fetch data from Device."""

        try:
            # device info is cached and won't be refetched on every
            # coordinator refresh, only after the device has disconnected
            # the device info is refetched
            self.device_info = await self.device.get_device_info()
            self.update_device_info()
            return await self.device.get_live_data()

        except CommunicationError:
            _LOGGER.debug("Cannot connect to device", exc_info=True)
            return self.data

    def update_device_info(self) -> None:
        """Update data in config entry for DeviceInfo."""

        update_info = {}
        if self.config_entry.data.get(CONF_SERIAL_NUMBER) is None:
            update_info[CONF_SERIAL_NUMBER] = self.device_info.device_sn
            update_info[CONF_DEVICE_ID] = self.device_info.device_id

        if (
            self.device_info.build
            and self.device_info.build != self.config_entry.data.get(CONF_SW_VERSION)
        ):
            update_info[CONF_SW_VERSION] = self.device_info.build

        if update_info:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, **update_info},
            )


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
