"""DataUpdateCoordinator for Garmin Connect."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from aiogarmin import GarminAuth, GarminClient
from aiogarmin.exceptions import GarminAPIError, GarminAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_OAUTH1_TOKEN,
    CONF_OAUTH2_TOKEN,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class GarminConnectCoordinators:
    """Container for Garmin Connect coordinators."""

    core: CoreCoordinator


class BaseGarminCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base class for Garmin Connect coordinators."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{name}",
            update_interval=update_interval,
        )
        self.client = client
        self.auth = auth
        self.config_entry = entry

    async def _update_tokens_if_changed(self) -> None:
        """Update stored tokens if they changed during refresh."""
        current_oauth1 = self.config_entry.data.get(CONF_OAUTH1_TOKEN)
        current_oauth2 = self.config_entry.data.get(CONF_OAUTH2_TOKEN)

        if (
            self.auth.oauth1_token != current_oauth1
            or self.auth.oauth2_token != current_oauth2
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_OAUTH1_TOKEN: self.auth.oauth1_token,
                    CONF_OAUTH2_TOKEN: self.auth.oauth2_token,
                },
            )


class CoreCoordinator(BaseGarminCoordinator):
    """Coordinator for core data: summary, steps, sleep (~50 sensors)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GarminClient,
        auth: GarminAuth,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass, entry, client, auth, "core", timedelta(seconds=DEFAULT_UPDATE_INTERVAL)
        )


    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch core data from Garmin Connect."""
        try:
            data = await self.client.fetch_core_data()
            await self._update_tokens_if_changed()
        except GarminAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except GarminAPIError as err:
            raise UpdateFailed(f"Error fetching core data: {err}") from err
        return data
