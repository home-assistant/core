"""DataUpdateCoordinator for Garmin Connect."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from ha_garmin import GarminAuth, GarminClient
from ha_garmin.exceptions import GarminAPIError, GarminAuthError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

if TYPE_CHECKING:
    from . import GarminConnectConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class GarminConnectCoordinators:
    """Container for Garmin Connect coordinators."""

    core: CoreCoordinator


class CoreCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Garmin Connect data."""

    config_entry: GarminConnectConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GarminConnectConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_core",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.client = client
        self.auth = auth
        self._refresh_lock = asyncio.Lock()

    async def _update_tokens_if_changed(self) -> None:
        """Update stored tokens if they changed during refresh."""
        async with self._refresh_lock:
            if (
                self.auth.di_token != self.config_entry.data[CONF_TOKEN]
                or self.auth.di_refresh_token
                != self.config_entry.data[CONF_REFRESH_TOKEN]
                or self.auth.di_client_id != self.config_entry.data[CONF_CLIENT_ID]
            ):
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_TOKEN: self.auth.di_token,
                        CONF_REFRESH_TOKEN: self.auth.di_refresh_token,
                        CONF_CLIENT_ID: self.auth.di_client_id,
                    },
                )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Garmin Connect."""
        try:
            data = await self.client.fetch_core_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
            raise UpdateFailed(f"Error fetching core data: {err}") from err
        return data
