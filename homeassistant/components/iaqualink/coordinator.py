"""Data update coordinator for iaqualink."""

from datetime import timedelta
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

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

BACKOFF_MULTIPLIER = 1.5


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
        except AqualinkServiceThrottledException:
            current_interval = self.update_interval or UPDATE_INTERVAL
            self.update_interval = timedelta(
                seconds=current_interval.total_seconds() * BACKOFF_MULTIPLIER
            )
            _LOGGER.debug(
                "iAquaLink system %s is rate-limited, increasing update interval to %ss",
                self.system.serial,
                self.update_interval.total_seconds(),
            )
            return
        except (AqualinkServiceException, httpx.HTTPError) as err:
            raise UpdateFailed(
                f"Unable to update iAquaLink system {self.system.serial}: {err}"
            ) from err
        if self.system.online is not True:
            raise UpdateFailed(f"iAquaLink system {self.system.serial} is offline")
        if self.update_interval != UPDATE_INTERVAL:
            _LOGGER.debug(
                "iAquaLink system %s rate limit cleared, resetting update interval",
                self.system.serial,
            )
            self.update_interval = UPDATE_INTERVAL
