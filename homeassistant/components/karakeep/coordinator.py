"""Data update coordinator for the Karakeep integration."""

from datetime import timedelta
import logging

from aiokarakeep import (
    KarakeepApiError,
    KarakeepAuthError,
    KarakeepClient,
    KarakeepConnectionError,
    KarakeepInvalidResponseError,
    KarakeepStats,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type KarakeepConfigEntry = ConfigEntry[KarakeepDataUpdateCoordinator]


class KarakeepDataUpdateCoordinator(DataUpdateCoordinator[KarakeepStats]):
    """Class to manage fetching Karakeep data."""

    config_entry: KarakeepConfigEntry

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
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )

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
