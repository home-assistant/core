"""Coordinator to update data from Aquacell API."""
from datetime import timedelta
import logging

from aioaquacell import (
    AquacellApi,
    AquacellApiException,
    AuthenticationFailed,
    Softener,
)
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)


class AquacellCoordinator(DataUpdateCoordinator[list[Softener]]):
    """My custom coordinator."""

    def __init__(
        self, hass: HomeAssistant, aquacell_api: AquacellApi, entry: ConfigEntry
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Aquacell Coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=3600),
        )

        self.config_entry: ConfigEntry = entry
        self.refresh_token = entry.data[CONF_REFRESH_TOKEN]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.aquacell_api = aquacell_api

    async def _async_update_data(self) -> list[Softener]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            if self.refresh_token is None:
                raise ConfigEntryError("No token available.")

            async with async_timeout.timeout(10):
                _LOGGER.debug("Logging in using: %s", self.refresh_token)

                try:
                    await self.aquacell_api.authenticate_refresh(self.refresh_token)
                except AuthenticationFailed as err:
                    _LOGGER.debug(
                        "Authentication using refresh token failed due to: %s", err
                    )
                    _LOGGER.debug("Attempting to renew refresh token")
                    await self.aquacell_api.authenticate(self.username, self.password)
                    self.refresh_token = self.aquacell_api.refresh_token
                    self._update_config_entry_refresh_token()

                _LOGGER.debug("Logged in, new token: %s", self.aquacell_api.id_token)
                return await self.aquacell_api.get_all_softeners()
        except AuthenticationFailed as err:
            raise ConfigEntryAuthFailed from err
        except AquacellApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _update_config_entry_refresh_token(self) -> None:
        """Update or delete the refresh_token in the Config Entry."""
        data = {
            **self.config_entry.data,
            CONF_REFRESH_TOKEN: self.refresh_token,
        }

        self.hass.config_entries.async_update_entry(self.config_entry, data=data)
