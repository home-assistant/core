"""DataUpdateCoordinator for Kiosker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from kiosker import Blackout, KioskerAPI, ScreensaverState, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_API_TOKEN, CONF_SSL, CONF_SSL_VERIFY, DOMAIN, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

type KioskerConfigEntry = ConfigEntry[KioskerDataUpdateCoordinator]


@dataclass
class KioskerData:
    """Data structure for Kiosker integration."""

    status: Status
    blackout: Blackout
    screensaver: ScreensaverState


class KioskerDataUpdateCoordinator(DataUpdateCoordinator[KioskerData]):
    """Class to manage fetching data from the Kiosker API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KioskerConfigEntry,
    ) -> None:
        """Initialize."""
        self.api = KioskerAPI(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            token=config_entry.data[CONF_API_TOKEN],
            ssl=config_entry.data.get(CONF_SSL, False),
            verify=config_entry.data.get(CONF_SSL_VERIFY, False),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> KioskerData:
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
            raise UpdateFailed("Connection failed") from exception
        except Exception as exception:
            # Check if this is an authentication error (401)
            if self._is_auth_error(exception):
                _LOGGER.warning("Authentication failed for Kiosker: %s", exception)
                raise ConfigEntryError("Authentication failed") from exception

            _LOGGER.debug("Failed to update Kiosker data: %s", exception, exc_info=True)
            raise UpdateFailed("Unknown error") from exception
        else:
            return KioskerData(
                status=status,
                blackout=blackout,
                screensaver=screensaver,
            )

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
