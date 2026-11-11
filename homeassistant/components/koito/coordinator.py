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
        try:
            raw = await self.api.async_fetch_data(period="all_time")
        except KoitoAuthenticationError as err:
            raise ConfigEntryAuthFailed("Koito rejected the API key") from err
        except KoitoConnectionError as err:
            raise UpdateFailed(
                f"Unable to refresh Koito data: {err}", retry_after=err.retry_after
            ) from err
        except KoitoResponseError as err:
            raise UpdateFailed(f"Unable to refresh Koito data: {err}") from err

        return project_data(raw, self.api.base_url)
