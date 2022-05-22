"""Data update coordinator for the Radarr integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import cast

from aiopyarr import RootFolder, exceptions
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.models.request import SystemStatus
from aiopyarr.radarr_client import RadarrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class RadarrDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Radarr integration."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        host_configuration: PyArrHostConfiguration,
        api_client: RadarrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api_client = api_client
        self.disk_space: list[RootFolder] = []
        self.host_configuration = host_configuration
        self.movies: int = 0
        self.system_status: SystemStatus = SystemStatus({"": ""})

    async def _async_update_data(self) -> None:
        """Get the latest data from Radarr."""
        reg = er.async_get(self.hass)
        try:
            [self.system_status, self.disk_space] = await asyncio.gather(
                *[
                    self.api_client.async_get_system_status(),
                    self.api_client.async_get_root_folders(),
                ]
            )
            if (entry := reg.async_get("sensor.radarr_movies")) and not entry.disabled:
                self.movies = len(cast(list, await self.api_client.async_get_movies()))

        except exceptions.ArrConnectionException as ex:
            raise UpdateFailed(ex) from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex
