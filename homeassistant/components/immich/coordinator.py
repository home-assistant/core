"""Coordinator for the Immich integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from aioimmich import Immich
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichUnauthorizedError
from aioimmich.server.models import (
    ImmichServerAbout,
    ImmichServerStatistics,
    ImmichServerStorage,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ImmichData:
    """Data class for storing data from the API."""

    server_about: ImmichServerAbout
    server_storage: ImmichServerStorage
    server_usage: ImmichServerStatistics


type ImmichConfigEntry = ConfigEntry[ImmichDataUpdateCoordinator]


class ImmichDataUpdateCoordinator(DataUpdateCoordinator[ImmichData]):
    """Class to manage fetching IMGW-PIB data API."""

    config_entry: ImmichConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: Immich) -> None:
        """Initialize the data update coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> ImmichData:
        """Update data via internal method."""
        try:
            server_about = await self.api.server.async_get_about_info()
            server_storage = await self.api.server.async_get_storage_info()
            server_usage = await self.api.server.async_get_server_statistics()
        except ImmichUnauthorizedError as err:
            raise ConfigEntryAuthFailed from err
        except CONNECT_ERRORS as err:
            raise UpdateFailed from err

        return ImmichData(server_about, server_storage, server_usage)
