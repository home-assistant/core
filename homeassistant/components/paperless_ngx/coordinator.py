"""Paperless-ngx Status coordinator."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from typing import TypeVar

from pypaperless import Paperless
from pypaperless.exceptions import (
    PaperlessConnectionError,
    PaperlessForbiddenError,
    PaperlessInactiveOrDeletedError,
    PaperlessInvalidTokenError,
)
from pypaperless.models import RemoteVersion, Statistic, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type PaperlessConfigEntry = ConfigEntry[PaperlessData]

TData = TypeVar("TData")

UPDATE_INTERVAL_STATISTICS = timedelta(seconds=120)
UPDATE_INTERVAL_STATUS = timedelta(seconds=300)
UPDATE_INTERVAL_REMOTE_VERSION = timedelta(hours=24)


@dataclass
class PaperlessData:
    """Data for the Paperless-ngx integration."""

    statistics: PaperlessStatisticCoordinator
    status: PaperlessStatusCoordinator
    version: PaperlessVersionCoordinator


class PaperlessCoordinator(DataUpdateCoordinator[TData]):
    """Coordinator to manage fetching Paperless-ngx API."""

    config_entry: PaperlessConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize Paperless-ngx statistics coordinator."""
        self.api = api

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=name,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> TData:
        """Update data via internal method."""
        try:
            return await self._async_update_data_internal()
        except PaperlessConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except PaperlessInvalidTokenError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PaperlessInactiveOrDeletedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="user_inactive_or_deleted",
            ) from err
        except PaperlessForbiddenError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="forbidden",
            ) from err

    @abstractmethod
    async def _async_update_data_internal(self) -> TData:
        """Update data via paperless-ngx API."""


class PaperlessStatisticCoordinator(PaperlessCoordinator[Statistic]):
    """Coordinator to manage Paperless-ngx statistic updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
    ) -> None:
        """Initialize Paperless-ngx status coordinator."""
        super().__init__(
            hass,
            entry,
            api,
            name="Statistics Coordinator",
            update_interval=UPDATE_INTERVAL_STATISTICS,
        )

    async def _async_update_data_internal(self) -> Statistic:
        """Fetch statistics data from API endpoint."""
        return await self.api.statistics()


class PaperlessStatusCoordinator(PaperlessCoordinator[Status]):
    """Coordinator to manage Paperless-ngx status updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
    ) -> None:
        """Initialize Paperless-ngx status coordinator."""
        super().__init__(
            hass,
            entry,
            api,
            name="Status Coordinator",
            update_interval=UPDATE_INTERVAL_STATUS,
        )

    async def _async_update_data_internal(self) -> Status:
        """Fetch status data from API endpoint."""
        return await self.api.status()


class PaperlessVersionCoordinator(PaperlessCoordinator[RemoteVersion]):
    """Coordinator to manage Paperless-ngx remote version updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessConfigEntry,
        api: Paperless,
    ) -> None:
        """Initialize Paperless-ngx remote version coordinator."""
        super().__init__(
            hass,
            entry,
            api,
            name="Remote Version Coordinator",
            update_interval=UPDATE_INTERVAL_REMOTE_VERSION,
        )

    async def _async_update_data_internal(self) -> RemoteVersion:
        """Fetch remote version data from API endpoint."""
        remote_version = await self.api.remote_version()
        if not remote_version.version or remote_version.version == "v0.0.0":
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="remote_version_not_available",
            )
        return remote_version
