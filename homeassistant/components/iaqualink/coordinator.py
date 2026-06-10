"""Data update coordinator for iaqualink."""

import logging
from typing import Any

import httpx
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_BY_SYSTEM_TYPE, UPDATE_INTERVAL_DEFAULT
from .utils import error_detail

_LOGGER = logging.getLogger(__name__)


class AqualinkDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data coordinator for Aqualink systems."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, system: Any
    ) -> None:
        """Initialize the coordinator."""
        update_interval = UPDATE_INTERVAL_BY_SYSTEM_TYPE.get(
            system.NAME, UPDATE_INTERVAL_DEFAULT
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{system.serial}",
            update_interval=update_interval,
        )
        self.system = system

    async def _async_update_data(self) -> None:
        """Refresh internal state for a system."""
        try:
            await self.system.update()
        except AqualinkServiceUnauthorizedException as err:
            raise ConfigEntryAuthFailed("Invalid credentials for iAquaLink") from err
        except AqualinkServiceThrottledException:
            _LOGGER.warning(
                "Rate limited by iAquaLink system %s, will retry later",
                self.system.serial,
            )
            return
        except (AqualinkServiceException, TimeoutError, httpx.HTTPError) as err:
            raise UpdateFailed(
                "Unable to update iAquaLink system "
                f"{self.system.serial}: {error_detail(err)}"
            ) from err
        if self.system.online is not True:
            raise UpdateFailed(f"iAquaLink system {self.system.serial} is offline")
