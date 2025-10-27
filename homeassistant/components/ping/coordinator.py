"""DataUpdateCoordinator for the ping integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import SLOW_UPDATE_WARNING
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .helpers import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)

type PingConfigEntry = ConfigEntry[PingUpdateCoordinator]


@dataclass(slots=True, frozen=True)
class PingResult:
    """Dataclass returned by the coordinator."""

    ip_address: str
    is_alive: bool
    data: dict[str, Any]


class PingUpdateCoordinator(DataUpdateCoordinator[PingResult]):
    """The Ping update coordinator."""

    config_entry: PingConfigEntry
    ping: PingDataSubProcess | PingDataICMPLib

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PingConfigEntry,
        ping: PingDataSubProcess | PingDataICMPLib,
    ) -> None:
        """Initialize the Ping coordinator."""
        self.ping = ping
        self._update_task: asyncio.Task[None] | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Ping {ping.ip_address}",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> PingResult:
        """Update ping data within a timeout duration."""

        if self._update_task is None:
            # queue a task for pinging.
            # this is done so that pings can have a duration longer than SLOW_UPDATE_WARNING,
            # but this method never executes for longer than SLOW_UPDATE_WARNING (we just
            # might report stale results in the meanwhile)
            self._update_task = asyncio.create_task(self.ping.async_update())

        with suppress(asyncio.TimeoutError):
            warning_buffer_time = 1
            await asyncio.wait_for(
                asyncio.shield(self._update_task),
                timeout=SLOW_UPDATE_WARNING - warning_buffer_time,
            )
            self._update_task = None

        # regardless of whether we exited the above block via a timeout or not,
        # we return the latest results - either those we just got, or a
        # previous set (in the case that we timed out above)
        return self._latest_ping_result()

    def _latest_ping_result(self) -> PingResult:
        return PingResult(
            ip_address=self.ping.ip_address,
            is_alive=self.ping.is_alive,
            data=self.ping.data or {},
        )
