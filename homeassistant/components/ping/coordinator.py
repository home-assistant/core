"""DataUpdateCoordinator for the ping integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Ping {ping.ip_address}",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> PingResult:
        """Trigger ping check."""
        await self.ping.async_update()
        return PingResult(
            ip_address=self.ping.ip_address,
            is_alive=self.ping.is_alive,
            data=self.ping.data or {},
        )
