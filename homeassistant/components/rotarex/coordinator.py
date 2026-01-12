"""DataUpdateCoordinator for the Rotarex integration."""

from datetime import timedelta
import logging
from typing import Any

from rotarex_dimes_srg_api import InvalidAuth, RotarexApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RotarexDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching Rotarex data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: RotarexApi,
        email: str,
        password: str,
    ) -> None:
        """Initialize the data update coordinator."""
        self.api = api
        self._email = email
        self._password = password
        self.api.set_credentials(email, password)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API endpoint."""
        try:
            return await self.api.fetch_tanks()
        except InvalidAuth as err:
            _LOGGER.warning("Token expired, attempting to re-login: %s", err)
            try:
                await self.api.login(self._email, self._password)
            except InvalidAuth as login_err:
                raise ConfigEntryAuthFailed(
                    f"Re-authentication failed: {login_err}"
                ) from login_err
            return await self.api.fetch_tanks()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
