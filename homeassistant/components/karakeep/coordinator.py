"""Data update coordinator for the Karakeep integration."""

from dataclasses import dataclass
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


@dataclass
class KarakeepData:
    """Data fetched from Karakeep."""

    stats: KarakeepStats
    version: str | None


class KarakeepDataUpdateCoordinator(DataUpdateCoordinator[KarakeepData]):
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
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> KarakeepData:
        """Fetch data from Karakeep API."""
        try:
            stats = await self.client.async_get_stats()
        except KarakeepAuthError as err:
            raise ConfigEntryAuthFailed("Invalid Karakeep API token") from err
        except KarakeepConnectionError as err:
            raise UpdateFailed(f"Error communicating with Karakeep: {err}") from err
        except (KarakeepApiError, KarakeepInvalidResponseError) as err:
            raise UpdateFailed(f"Invalid response from Karakeep: {err}") from err

        # The version is optional and must never fail the data update.
        try:
            version = await self.client.async_get_version()
        except KarakeepError as err:
            _LOGGER.debug("Could not fetch Karakeep version: %s", err)
            version = None

        return KarakeepData(stats=stats, version=version)
