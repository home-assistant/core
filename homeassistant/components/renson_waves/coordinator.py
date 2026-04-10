"""DataUpdateCoordinator for Renson WAVES."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RensonWavesCannotConnect, RensonWavesClient
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class RensonWavesData:
    """Data returned by RensonWavesCoordinator._async_update_data."""

    constellation: dict[str, Any]
    wifi_status: dict[str, Any]
    uptime: dict[str, Any]
    decision_room: dict[str, Any]
    decision_silent: dict[str, Any]
    decision_breeze: dict[str, Any]


class RensonWavesCoordinator(DataUpdateCoordinator[RensonWavesData]):
    """Coordinator for Renson WAVES device."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RensonWavesClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> RensonWavesData:
        """Fetch data from API."""
        try:
            # Fetch constellation (required) and optional endpoints in parallel
            (
                constellation,
                wifi_status,
                uptime,
                decision_room,
                decision_silent,
                decision_breeze,
            ) = await asyncio.gather(
                self.client.async_get_constellation(),
                self.client.async_get_wifi_status(),
                self.client.async_get_global_uptime(),
                self.client.async_get_decision_room(),
                self.client.async_get_decision_silent(),
                self.client.async_get_decision_breeze(),
                return_exceptions=True,
            )

            # Check if constellation fetch failed
            if isinstance(constellation, Exception):
                raise constellation

            # Wrap other optional fetches that might be exceptions
            if isinstance(wifi_status, Exception):
                wifi_status = {}
            if isinstance(uptime, Exception):
                uptime = {}
            if isinstance(decision_room, Exception):
                decision_room = {}
            if isinstance(decision_silent, Exception):
                decision_silent = {}
            if isinstance(decision_breeze, Exception):
                decision_breeze = {}

            return RensonWavesData(
                constellation=constellation,
                wifi_status=wifi_status,
                uptime=uptime,
                decision_room=decision_room,
                decision_silent=decision_silent,
                decision_breeze=decision_breeze,
            )

        except RensonWavesCannotConnect as err:
            raise UpdateFailed(f"Cannot connect to device: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
