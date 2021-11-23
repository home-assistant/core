"""Data update coordinator for the Radarr integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import time

from aiopyarr import RadarrClient, exceptions
from aiopyarr.models.radarr import RadarrCalendar, RadarrCommand, RadarrDiskspace, RadarrMovie, RadarrSystemStatus
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER
import logging

_LOGGER = logging.getLogger(__name__)


class RadarrDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Radarr integration."""

    def __init__(
        self,
        hass: HomeAssistant,
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
        self.disk_space: list[RadarrDiskspace] | None = None
        self.calendar: list[RadarrCalendar] | None  = None
        self.movies: list[RadarrMovie] | None = None
        self.system_status: RadarrSystemStatus | None = None
        self.commands: list[RadarrCommand] | None = None
        self.days = 7

    #TODO Remove
    ENDPOINTS = {
        "diskspace": "{0}://{1}:{2}/{3}api/diskspace",
        "upcoming": "{0}://{1}:{2}/{3}api/calendar?start={4}&end={5}",
        "movies": "{0}://{1}:{2}/{3}api/movie",
        "commands": "{0}://{1}:{2}/{3}api/command",
        "status": "{0}://{1}:{2}/{3}api/system/status",
    }

    async def _async_update_data(self) -> None:
        """Get the latest data from Radarr."""
        time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
        start = get_date(time_zone)
        end = get_date(time_zone, self.days)
        try:
            #self.disk_space = await self.api_client.async_get_diskspace()
            [self.calendar, self.movies, self.commands, self.system_status] = await asyncio.gather(
            #[self.system_status] = await asyncio.gather(
                *[
                    #self.api_client.async_get_diskspace(),
                    self.api_client.async_get_calendar(start, end), #TODO get start and end date
                    self.api_client.async_get_movies(),
                    self.api_client.async_get_command(),
                    self.api_client.async_get_system_status(),
                ]
            )
            #_LOGGER.warning(self.system_status)
        except exceptions.ArrConnectionException as ex:
            if self.config_entry and self.config_entry.state == ConfigEntryState.LOADED:
                raise UpdateFailed(ex) from ex
            raise ConfigEntryNotReady from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed("API Key is no longer valid. Please reauthenticate") from ex

def get_date(zone: str, offset: int = 0) -> str:
    """Get date based on timezone and offset of days."""
    day = 60 * 60 * 24
    return datetime.date(datetime.fromtimestamp(time.time() + day * offset, tz=zone))