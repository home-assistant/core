"""Data update coordinator for the Radarr integration."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, tzinfo
import time
from typing import cast

from aiopyarr import exceptions
from aiopyarr.models import radarr
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_UPCOMING_DAYS, DOMAIN, LOGGER


class RadarrDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Radarr integration."""

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
        self.agg_space: dict = {}
        self.api_client = api_client
        self.calendar: list[radarr.RadarrCalendar] | None = None
        self.commands: list[radarr.RadarrCommand] | None = None
        self.disk_space: list[radarr.RadarrRootFolder] | None = None
        self.get_space = True
        self.host_configuration = host_configuration
        self.movies: list[radarr.RadarrMovie] | None = None
        self.movies_count_enabled: bool = False
        self.system_status = radarr.RadarrSystemStatus

    async def _async_update_data(self) -> None:
        """Get the latest data from Radarr."""
        time_zone = cast(tzinfo, dt_util.get_time_zone(self.hass.config.time_zone))
        assert isinstance(self.config_entry, ConfigEntry)
        upcoming = self.config_entry.options.get(CONF_UPCOMING_DAYS, 7)
        start = get_date(time_zone)
        end = get_date(time_zone, upcoming)
        try:
            [
                self.disk_space,
                self.calendar,
                self.commands,
                self.system_status,
            ] = await asyncio.gather(
                *[
                    self.api_client.async_get_root_folders(),
                    self.api_client.async_get_calendar(start, end),
                    self.api_client.async_get_command(),
                    self.api_client.async_get_system_status(),
                ]
            )
            # Diskspace can timeout with large systems with remote mapped storage
            if self.agg_space is not None and len(self.agg_space) == 0:
                mounts = await self.api_client.async_get_diskspace()
                for mount in mounts:
                    self.agg_space[mount.totalSpace] = mount.freeSpace
            elif self.movies_count_enabled is True:
                # Wait to get movie count after disk capacity is determined
                self.movies = await self.api_client.async_get_movies()

        except (
            exceptions.ArrConnectionException,
            asyncio.exceptions.TimeoutError,
        ) as ex:
            # We attempt to get total disk capacity once
            if not self.get_space:
                if (
                    self.config_entry
                    and self.config_entry.state == ConfigEntryState.LOADED
                ):
                    raise UpdateFailed(ex) from ex
                raise ConfigEntryNotReady from ex
            self.get_space = False
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex


def get_date(zone: tzinfo, offset: int = 0) -> date:
    """Get date based on timezone and offset of days."""
    day = 60 * 60 * 24
    return datetime.date(datetime.fromtimestamp(time.time() + day * offset, tz=zone))
