"""Data update coordinator for iaqualink."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AqualinkDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data coordinator for Aqualink systems."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, system: Any
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{system.serial}",
            update_interval=UPDATE_INTERVAL,
        )
        self.system = system

    async def _async_update_data(self) -> None:
        """Refresh internal state for a system."""
        try:
            await self.system.update()
        except AqualinkServiceUnauthorizedException as err:
            raise ConfigEntryAuthFailed("Invalid credentials for iAquaLink") from err
        except (AqualinkServiceException, httpx.HTTPError) as err:
            raise UpdateFailed(
                f"Unable to update iAquaLink system {self.system.serial}: {err}"
            ) from err
        if self.system.online is not True:
            raise UpdateFailed(f"iAquaLink system {self.system.serial} is offline")
