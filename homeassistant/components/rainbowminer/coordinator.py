"""Data update coordinator for the RainbowMiner integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from rainbowminer_api_client import (
    ActiveMiner,
    Balance,
    BinaryResponse,
    CurrentProfit,
    RainbowMinerAuthError,
    RainbowMinerClient,
    RainbowMinerError,
    Status,
    Uptime,
    Version,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


@dataclass
class RainbowMinerData:
    """Data class to hold all RainbowMiner state."""

    status: Status
    current_profit: CurrentProfit
    uptime: Uptime
    active_miners: list[ActiveMiner]
    version: Version
    balances: list[Balance]


type RainbowMinerConfigEntry = ConfigEntry[RainbowMinerCoordinator]


class RainbowMinerCoordinator(DataUpdateCoordinator[RainbowMinerData]):
    """Coordinator for polling RainbowMiner API state."""

    config_entry: RainbowMinerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: RainbowMinerConfigEntry,
        api: RainbowMinerClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    @override
    async def _async_setup(self) -> None:
        """Fetch the version once during setup."""
        try:
            await self.api.get_version()
        except RainbowMinerAuthError as err:
            raise ConfigEntryAuthFailed from err
        except RainbowMinerError as err:
            raise ConfigEntryNotReady from err

    @override
    async def _async_update_data(self) -> RainbowMinerData:
        """Fetch the latest data from the RainbowMiner API."""
        try:
            (
                status,
                current_profit,
                uptime,
                active_miners,
                version,
                balances,
            ) = await asyncio.gather(
                self.api.get_status(),
                self.api.get_current_profit(),
                self.api.get_uptime(),
                self.api.get_active_miners(),
                self.api.get_version(),
                self.api.get_balances(add_btc=True),
            )
        except RainbowMinerAuthError as err:
            raise ConfigEntryAuthFailed from err
        except RainbowMinerError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        if isinstance(balances, BinaryResponse):
            raise UpdateFailed("Unexpected binary response from balances endpoint")
        return RainbowMinerData(
            status,
            current_profit,
            uptime,
            active_miners,
            version,
            balances,
        )
