"""Data update coordinator for the Radarr integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, tzinfo
import time
from typing import TYPE_CHECKING, cast

from aiopyarr import exceptions

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_UPCOMING_DAYS, DOMAIN, LOGGER

if TYPE_CHECKING:
    from aiopyarr.models import radarr
    from aiopyarr.models.host_configuration import PyArrHostConfiguration
    from aiopyarr.radarr_client import RadarrClient

    from homeassistant.core import HomeAssistant


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
        self.calendar: list[radarr.RadarrCalendar] | None = None
        self.commands: list[radarr.RadarrCommand] | None = None
        self.disk_space: list[radarr.Diskspace] | None = None
        self.host_configuration = host_configuration
        self.movies: radarr.RadarrMovie | list[radarr.RadarrMovie] | None = None
        self.movies_count_enabled: bool = False
        self.rootfolder: list[radarr.RadarrRootFolder] | None = None
        self.system_status: radarr.RadarrSystemStatus | None = None

    async def _async_update_data(self) -> None:
        """Get the latest data from Radarr."""
        time_zone = cast(tzinfo, dt_util.get_time_zone(self.hass.config.time_zone))
        upcoming = self.config_entry.options[CONF_UPCOMING_DAYS]
        start = get_date(time_zone)
        end = get_date(time_zone, upcoming)
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
                    self.api_client.async_get_calendar(start, end),
                    self.api_client.async_get_command(),
                ]
            )
            # Diskspace can timeout with large systems with remote mapped storage
            # We attempt to get total disk capacity once
            if not self.disk_space:
                self.disk_space = await self.api_client.async_get_diskspace()
            elif self.movies_count_enabled is True:
                # Wait to get movie count after disk capacity is determined
                self.movies = await self.api_client.async_get_movies()

        except (
            exceptions.ArrConnectionException,
            asyncio.exceptions.TimeoutError,
        ) as ex:
            if self.config_entry and self.config_entry.state == ConfigEntryState.LOADED:
                raise UpdateFailed(ex) from ex
            raise ConfigEntryNotReady from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex


def get_date(zone: tzinfo, offset: int = 0) -> datetime:
    """Get date based on timezone and offset of days."""
    return datetime.fromtimestamp(time.time() + 60 * 60 * 24 * offset, tz=zone)
