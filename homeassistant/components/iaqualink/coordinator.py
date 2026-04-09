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
        self._logged_unavailable: set[str] = set()

    async def _async_update_data(self) -> None:
        """Refresh internal state for all systems."""
        for system in self.systems:
            prev = system.online

            try:
                await system.update()
            except AqualinkServiceException, httpx.HTTPError:
                if prev is not None and system.serial not in self._logged_unavailable:
                    self.logger.info("System %s unavailable", system.serial)
                    self._logged_unavailable.add(system.serial)
                await system.aqualink.close()
            else:
                cur = system.online
                if cur and system.serial in self._logged_unavailable:
                    self.logger.info(
                        "System %s reconnected to iAqualink", system.serial
                    )
                    self._logged_unavailable.discard(system.serial)
                elif not cur and prev and system.serial not in self._logged_unavailable:
                    self.logger.info("System %s unavailable", system.serial)
                    self._logged_unavailable.add(system.serial)
