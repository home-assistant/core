"""Data update coordinator for iaqualink."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from iaqualink.exception import AqualinkServiceException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AqualinkDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data coordinator for Aqualink systems."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, systems: list[Any]
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.systems = systems

    async def _async_update_data(self) -> None:
        """Refresh internal state for all systems."""
        for system in self.systems:
            prev = system.online

            try:
                await system.update()
            except AqualinkServiceException, httpx.HTTPError:
                if prev is not None:
                    self.logger.warning(
                        "Failed to refresh system %s state",
                        system.serial,
                    )
                await system.aqualink.close()
            else:
                cur = system.online
                if cur and not prev:
                    self.logger.warning(
                        "System %s reconnected to iAqualink", system.serial
                    )
