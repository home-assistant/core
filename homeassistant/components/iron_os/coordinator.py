"""Update coordinator for IronOS Integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import cast

from pynecil import (
    CharSetting,
    CommunicationError,
    DeviceInfoResponse,
    IronOSUpdate,
    LatestRelease,
    LiveDataResponse,
    Pynecil,
    SettingsDataResponse,
    UpdateException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
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


class IronOSFirmwareUpdateCoordinator(DataUpdateCoordinator[LatestRelease]):
    """IronOS coordinator for retrieving update information from github."""

    def __init__(self, hass: HomeAssistant, github: IronOSUpdate) -> None:
        """Initialize IronOS coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL_GITHUB,
        )
        self.github = github

    async def _async_update_data(self) -> LatestRelease:
        """Fetch data from Github."""

        try:
            return await self.github.latest_release()
        except UpdateException as e:
            raise UpdateFailed("Failed to check for latest IronOS update") from e


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

    async def write(self, characteristic: CharSetting, value: bool) -> None:
        """Write value to the settings characteristic."""

        try:
            await self.device.write(characteristic, value)
        except CommunicationError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="submit_setting_failed",
            ) from e

        # prevent switch bouncing while waiting for coordinator to finish refresh
        self.data.update(
            cast(SettingsDataResponse, {characteristic.name.lower(): value})
        )
        self.async_update_listeners()
        await self.async_request_refresh()
