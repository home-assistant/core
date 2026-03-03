"""Data update coordinator for the Cosa integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CosaApi, CosaAuthError, CosaConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=180)


class CosaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching Cosa thermostat data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: CosaApi,
        endpoint_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.api = api
        self.endpoint_id = endpoint_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data from the Cosa API."""
        try:
            data = await self.api.async_get_endpoint(self.endpoint_id)
        except CosaAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except CosaConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        if data is None:
            raise UpdateFailed(f"Failed to fetch data for endpoint {self.endpoint_id}")
        return data
