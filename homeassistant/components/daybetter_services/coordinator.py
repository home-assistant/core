"""DataUpdateCoordinator for DayBetter devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from daybetter_python import APIError, AuthenticationError, DayBetterClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DayBetterConfigEntry


class DayBetterCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator fetching DayBetter device data periodically."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DayBetterConfigEntry,
        client: DayBetterClient,
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name="DayBetter Coordinator",
            update_interval=interval,
            config_entry=config_entry,
        )
        self._client = client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API."""
        try:
            return await self._client.fetch_sensor_data()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except APIError as err:
            raise UpdateFailed(f"API error: {err}") from err
