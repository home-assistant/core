"""DataUpdateCoordinator for ntfy integration."""

from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aiontfy import Account as NtfyAccount, Ntfy, Version
from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyHTTPError,
    NtfyNotFoundPageError,
    NtfyTimeoutError,
    NtfyUnauthorizedAuthenticationError,
)
from aiontfy.update import LatestRelease, UpdateChecker, UpdateCheckerError
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type NtfyConfigEntry = ConfigEntry[NtfyRuntimeData]


@dataclass
class NtfyRuntimeData:
    """Holds ntfy runtime data."""

    account: NtfyDataUpdateCoordinator
    version: NtfyVersionDataUpdateCoordinator


class BaseDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Ntfy base coordinator."""

    config_entry: NtfyConfigEntry
    update_interval: timedelta

    def __init__(
        self, hass: HomeAssistant, config_entry: NtfyConfigEntry, ntfy: Ntfy
    ) -> None:
        """Initialize the ntfy data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self.update_interval,
        )

        self.ntfy = ntfy

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info of the ntfy account service device."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ntfy LLC",
            model="ntfy",
            configuration_url=URL(self.config_entry.data[CONF_URL]) / "app",
            identifiers={(DOMAIN, self.config_entry.entry_id)},
        )

    @abstractmethod
    async def async_update_data(self) -> _DataT:
        """Fetch the latest data from the source."""

    @override
    async def _async_update_data(self) -> _DataT:
        """Fetch the latest data from the source."""
        try:
            return await self.async_update_data()
        except NtfyHTTPError as e:
            _LOGGER.debug("Error %s: %s [%s]", e.code, e.error, e.link)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="server_error",
                translation_placeholders={"error_msg": str(e.error)},
            ) from e
        except NtfyConnectionError as e:
            _LOGGER.debug("Error", exc_info=True)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from e
        except NtfyTimeoutError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
            ) from e


class NtfyDataUpdateCoordinator(BaseDataUpdateCoordinator[NtfyAccount]):
    """Ntfy data update coordinator."""

    update_interval = timedelta(minutes=15)

    @override
    async def async_update_data(self) -> NtfyAccount:
        """Fetch account data from ntfy."""

        try:
            return await self.ntfy.account()
        except NtfyUnauthorizedAuthenticationError as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from e


class NtfyVersionDataUpdateCoordinator(BaseDataUpdateCoordinator[Version | None]):
    """Ntfy data update coordinator."""

    update_interval = timedelta(hours=3)

    @override
    async def async_update_data(self) -> Version | None:
        """Fetch version data from ntfy."""
        try:
            version = await self.ntfy.version()
        except NtfyUnauthorizedAuthenticationError, NtfyNotFoundPageError:
            # /v1/version endpoint is only accessible to admins and
            # available in ntfy since version 2.17.0
            return None
        return version


class NtfyLatestReleaseUpdateCoordinator(DataUpdateCoordinator[LatestRelease]):
    """Ntfy latest release update coordinator."""

    def __init__(self, hass: HomeAssistant, update_checker: UpdateChecker) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=timedelta(hours=3),
        )
        self.update_checker = update_checker

    @override
    async def _async_update_data(self) -> LatestRelease:
        """Fetch latest release data."""

        try:
            return await self.update_checker.latest_release()
        except UpdateCheckerError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_check_failed",
            ) from e
