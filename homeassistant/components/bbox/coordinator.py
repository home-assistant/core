"""Data update coordinator for the Bbox integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import override

from bbox_api import (
    BboxApiError,
    BboxAuthenticationError,
    BboxClient,
    BboxConnectionError,
    BboxTimeoutError,
    DeviceInfo as BboxDeviceInfo,
    Host,
    WANIPStats,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BboxData:
    """Data fetched from the Bbox in one update."""

    device: BboxDeviceInfo
    stats: WANIPStats
    hosts: list[Host]


type BboxConfigEntry = ConfigEntry[BboxCoordinator]


class BboxCoordinator(DataUpdateCoordinator[BboxData]):
    """Fetch the device info, the WAN stats and the hosts of the Bbox."""

    config_entry: BboxConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: BboxConfigEntry, client: BboxClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> BboxData:
        """Fetch all endpoints concurrently.

        The client serializes the login internally, so the concurrent
        calls share a single authentication round trip.
        """
        try:
            async with asyncio.TaskGroup() as tg:
                device_task = tg.create_task(self.client.get_device())
                stats_task = tg.create_task(self.client.get_wan_ip_stats())
                hosts_task = tg.create_task(self.client.get_hosts())
        except BaseExceptionGroup as err:
            # A failing request cancels its siblings, so the group carries
            # only the original error.
            result = err.exceptions[0]
            if isinstance(result, BboxAuthenticationError):
                raise ConfigEntryAuthFailed(
                    f"Authentication with the Bbox failed: {result}"
                ) from result
            if isinstance(result, (BboxConnectionError, BboxTimeoutError)):
                raise UpdateFailed(f"Cannot reach the Bbox: {result}") from result
            if isinstance(result, BboxApiError):
                raise UpdateFailed(f"Bbox API error: {result}") from result
            raise result from None
        return BboxData(
            device=device_task.result(),
            stats=stats_task.result(),
            hosts=hosts_task.result(),
        )
