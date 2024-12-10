"""Update coordinator for IronOS Integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiogithubapi import GitHubAPI, GitHubException, GitHubReleaseModel
from pynecil import (
    CommunicationError,
    DeviceInfoResponse,
    LiveDataResponse,
    Pynecil,
    SettingsDataResponse,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
SCAN_INTERVAL_GITHUB = timedelta(hours=3)
SCAN_INTERVAL_SETTINGS = timedelta(seconds=60)


@dataclass
class IronOSCoordinators:
    """IronOS data class holding coordinators."""

    live_data: IronOSLiveDataCoordinator
    settings: IronOSSettingsCoordinator


class IronOSBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """IronOS base coordinator."""

    device_info: DeviceInfoResponse
    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        device: Pynecil,
        update_interval: timedelta,
    ) -> None:
        """Initialize IronOS coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=3, immediate=False
            ),
        )
        self.device = device

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            self.device_info = await self.device.get_device_info()

        except CommunicationError as e:
            raise UpdateFailed("Cannot connect to device") from e


class IronOSLiveDataCoordinator(IronOSBaseCoordinator[LiveDataResponse]):
    """IronOS coordinator."""

    def __init__(self, hass: HomeAssistant, device: Pynecil) -> None:
        """Initialize IronOS coordinator."""
        super().__init__(hass, device=device, update_interval=SCAN_INTERVAL)

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

    @property
    def has_tip(self) -> bool:
        """Return True if the tip is connected."""
        if (
            self.data.max_tip_temp_ability is not None
            and self.data.live_temp is not None
        ):
            threshold = self.data.max_tip_temp_ability - 5
            return self.data.live_temp <= threshold
        return False


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


class IronOSSettingsCoordinator(IronOSBaseCoordinator[SettingsDataResponse]):
    """IronOS coordinator."""

    def __init__(self, hass: HomeAssistant, device: Pynecil) -> None:
        """Initialize IronOS coordinator."""
        super().__init__(hass, device=device, update_interval=SCAN_INTERVAL_SETTINGS)

    async def _async_update_data(self) -> SettingsDataResponse:
        """Fetch data from Device."""

        characteristics = set(self.async_contexts())

        if self.device.is_connected and characteristics:
            try:
                return await self.device.get_settings(list(characteristics))
            except CommunicationError as e:
                _LOGGER.debug("Failed to fetch settings", exc_info=e)

        return self.data or SettingsDataResponse()
