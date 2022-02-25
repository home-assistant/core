"""Data update coordinator for the Lidarr integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from math import ceil

from aiopyarr import LidarrQueue, LidarrWantedCutoff, SystemStatus, exceptions
from aiopyarr.lidarr_client import LidarrClient
from aiopyarr.models import lidarr
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.models.request import Command, Diskspace

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_GIGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import BYTE_SIZES, CONF_MAX_RECORDS, CONF_UPCOMING_DAYS, DOMAIN, LOGGER


class LidarrDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Lidarr integration."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        host_configuration: PyArrHostConfiguration,
        api_client: LidarrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api_client = api_client
        self.calendar: list[lidarr.LidarrCalendar] = []
        self.commands: list[Command] = []
        self.disk_space: list[Diskspace] = []
        self.host_configuration = host_configuration
        self.queue: LidarrQueue = LidarrQueue({"records": []})
        self.system_status: SystemStatus = SystemStatus({"": ""})
        self.wanted: LidarrWantedCutoff = LidarrWantedCutoff({"records": []})

    async def _async_update_data(self) -> None:
        """Get the latest data from Lidarr."""
        days = self.config_entry.options[CONF_UPCOMING_DAYS]
        records = self.config_entry.options[CONF_MAX_RECORDS]
        start = dt_util.as_utc(dt_util.start_of_local_day().replace(microsecond=0))
        end = start + timedelta(days=days)
        try:
            [
                self.calendar,
                self.commands,
                self.disk_space,
                self.queue,
                self.system_status,
                self.wanted,
            ] = await asyncio.gather(
                *[
                    self.api_client.async_get_calendar(start_date=start, end_date=end),
                    self.api_client.async_get_commands(),
                    self.api_client.async_get_diskspace(),
                    self.api_client.async_get_queue(page_size=records),
                    self.api_client.async_get_system_status(),
                    self.api_client.async_get_wanted(page_size=records),
                ]
            )

        except exceptions.ArrConnectionException as ex:
            raise UpdateFailed(ex) from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex
        unit = 1024 ** BYTE_SIZES.index(DATA_GIGABYTES)
        space = {f"{ceil(m.freeSpace/unit)}{m.totalSpace}": m for m in self.disk_space}
        self.disk_space = list(p for p in space.values())  # noqa: C400
