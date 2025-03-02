"""Data update coordinator for Version entities."""

from __future__ import annotations

from typing import Any

from awesomeversion import AwesomeVersion
from pyhaversion import HaVersion, HaVersionSource
from pyhaversion.exceptions import HaVersionException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_COORDINATOR_UPDATE_INTERVAL

type VersionConfigEntry = ConfigEntry[VersionDataUpdateCoordinator]


class VersionDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for Version entities."""

    config_entry: VersionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: VersionConfigEntry,
        api: HaVersion,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_COORDINATOR_UPDATE_INTERVAL,
        )
        self._api = api
        self._version: AwesomeVersion | None = None
        self._version_data: dict[str, Any] | None = None

    @property
    def version(self) -> str | None:
        """Return the latest version."""
        return str(self._version) if self._version else None

    @property
    def version_data(self) -> dict[str, Any] | None:
        """Return the version data."""
        if self._api.source == HaVersionSource.LOCAL:
            return None
        return self._version_data or {}

    async def _async_update_data(self) -> None:
        """Update version data."""
        try:
            self._version, self._version_data = await self._api.get_version()
        except HaVersionException as exception:
            raise UpdateFailed(exception) from exception
