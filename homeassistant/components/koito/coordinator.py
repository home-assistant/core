"""Polling coordinator for Koito data."""

import logging
from typing import override

from aiokoito import (
    KoitoApi,
    KoitoAuthenticationError,
    KoitoConnectionError,
    KoitoResponseError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL
from .models import KoitoData, project_data

_LOGGER = logging.getLogger(__name__)
type KoitoConfigEntry = ConfigEntry[KoitoCoordinator]


class KoitoCoordinator(DataUpdateCoordinator[KoitoData]):
    """Fetch and project Koito statistics and playback for entity presentation."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: KoitoConfigEntry,
        api: KoitoApi,
    ) -> None:
        """Initialize one server's polling coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Koito",
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.api = api

    @override
    async def _async_update_data(self) -> KoitoData:
        """Fetch all-time data, respecting authentication and server backoff."""
        failed = False
        auth_failed = False
        retry_after = None
        try:
            raw = await self.api.async_fetch_data(period="all_time")
        except KoitoAuthenticationError:
            auth_failed = True
        except KoitoConnectionError as err:
            failed = True
            retry_after = err.retry_after
        except KoitoResponseError:
            failed = True
        if auth_failed:
            raise ConfigEntryAuthFailed("Koito rejected the API key")
        if failed:
            raise UpdateFailed("Unable to refresh Koito data", retry_after=retry_after)

        return project_data(raw, self.api.base_url)
