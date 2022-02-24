"""Data update coordinator for the Radarr integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import cast

from aiopyarr import Command, Diskspace, RootFolder, exceptions
from aiopyarr.models import radarr
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.models.request import SystemStatus
from aiopyarr.radarr_client import RadarrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_UPCOMING_DAYS, DOMAIN


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
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api_client = api_client
        self.calendar: list[radarr.RadarrCalendar] = []
        self.commands: list[Command] = []
        self.disk_space: list[Diskspace] = []
        self.host_configuration = host_configuration
        self.movies: list[radarr.RadarrMovie] = []
        self.movies_count_enabled: bool = False
        self.rootfolder: list[RootFolder] = []
        self.system_status: SystemStatus = SystemStatus({"": ""})

    async def _async_update_data(self) -> None:
        """Get the latest data from Radarr."""
        start = dt_util.as_utc(dt_util.start_of_local_day().replace(microsecond=0))
        end = start + timedelta(days=self.config_entry.options[CONF_UPCOMING_DAYS])
        try:
            [
                self.system_status,
                self.rootfolder,
                self.calendar,
                self.commands,
            ] = await asyncio.gather(
                *[
                    self.api_client.async_get_system_status(),
                    self.api_client.async_get_root_folders(),
                    self.api_client.async_get_calendar(start_date=start, end_date=end),
                    self.api_client.async_get_commands(),
                ]
            )
            # Diskspace can timeout with large systems with remote mapped storage
            # We attempt to get total disk capacity first
            if not self.disk_space and not self.movies_count_enabled:
                self.disk_space = await self.api_client.async_get_diskspace()
            else:
                # Wait to get movie count after disk capacity is determined
                self.movies_count_enabled = True
                self.movies = cast(list, await self.api_client.async_get_movies())

        except exceptions.ArrConnectionException as ex:
            raise UpdateFailed(ex) from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex
