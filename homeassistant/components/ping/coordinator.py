"""DataUpdateCoordinator for the ping integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .ping import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PingResult:
    """Dataclass returned by the coordinator."""

    is_alive: bool
    data: dict[str, Any] | None


class PingUpdateCoordinator(DataUpdateCoordinator[PingResult]):
    """The Ping update coordinator."""

    ping: PingDataSubProcess | PingDataICMPLib

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        ping: PingDataSubProcess | PingDataICMPLib,
    ) -> None:
        """Initialize the Ping coordinator."""
        self.config_entry = config_entry
        self.ping = ping

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> PingResult:
        """Trigger ping check."""
        await self.ping.async_update()
        return PingResult(is_alive=self.ping.is_alive, data=self.ping.data)
