"""DataUpdateCoordinator for Fluss+ integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from fluss_api.main import FlussApiClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = 60  # seconds


class FlussDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages fetching Fluss device data on a schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FlussApiClient,
        api_key: str,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=f"Fluss+ ({slugify(api_key[:8])})",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Fluss API."""
        try:
            return await self.api.async_get_devices()
        except Exception as err:
            raise UpdateFailed(f"Error fetching Fluss data: {err}") from err
