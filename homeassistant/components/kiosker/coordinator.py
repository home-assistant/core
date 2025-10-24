"""DataUpdateCoordinator for Kiosker."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from kiosker import KioskerAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class KioskerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Kiosker API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: KioskerAPI,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            status = await self.hass.async_add_executor_job(self.api.status)
            blackout = await self.hass.async_add_executor_job(self.api.blackout_get)
            screensaver = await self.hass.async_add_executor_job(
                self.api.screensaver_get_state
            )
        except (OSError, TimeoutError) as exception:
            _LOGGER.warning(
                "Connection failed for Kiosker: %s", exception, exc_info=True
            )
            raise UpdateFailed(exception) from exception
        except Exception as exception:
            # Check if this is an authentication error (401)
            if self._is_auth_error(exception):
                _LOGGER.warning("Authentication failed for Kiosker: %s", exception)
                raise ConfigEntryAuthFailed("Authentication failed") from exception

            _LOGGER.warning(
                "Failed to update Kiosker data: %s", exception, exc_info=True
            )
            raise UpdateFailed(exception) from exception
        else:
            return {
                "status": status,
                "blackout": blackout,
                "screensaver": screensaver,
            }

    def _is_auth_error(self, exception: Exception) -> bool:
        """Check if exception indicates authentication failure."""
        error_str = str(exception).lower()
        # Check for common HTTP 401/authentication error patterns
        return (
            "401" in error_str
            or "unauthorized" in error_str
            or "authentication" in error_str
            or "invalid token" in error_str
            or "access denied" in error_str
        )
