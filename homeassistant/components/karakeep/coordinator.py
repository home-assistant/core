"""Data update coordinator for the Karakeep integration."""

import logging

from aiokarakeep import (
    KarakeepApiError,
    KarakeepAuthError,
    KarakeepClient,
    KarakeepConnectionError,
    KarakeepError,
    KarakeepInvalidResponseError,
    KarakeepStats,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type KarakeepConfigEntry = ConfigEntry[KarakeepDataUpdateCoordinator]


class KarakeepDataUpdateCoordinator(DataUpdateCoordinator[KarakeepStats]):
    """Class to manage fetching Karakeep data."""

    config_entry: KarakeepConfigEntry
    version: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: KarakeepConfigEntry,
        client: KarakeepClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

    async def _async_setup(self) -> None:
        """Fetch the server version once during setup."""
        # The version is optional and must never fail setup.
        try:
            self.version = await self.client.async_get_version()
        except KarakeepError as err:
            _LOGGER.debug("Could not fetch Karakeep version: %s", err)

    async def _async_update_data(self) -> KarakeepStats:
        """Fetch data from Karakeep API."""
        try:
            return await self.client.async_get_stats()
        except KarakeepAuthError as err:
            raise ConfigEntryAuthFailed("Invalid Karakeep API token") from err
        except KarakeepConnectionError as err:
            raise UpdateFailed(f"Error communicating with Karakeep: {err}") from err
        except (KarakeepApiError, KarakeepInvalidResponseError) as err:
            raise UpdateFailed(f"Invalid response from Karakeep: {err}") from err
