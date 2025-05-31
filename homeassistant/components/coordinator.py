"""Coordinator module for the Grid Connect integration.

Handles periodic polling of data from local Grid Connect devices
and distributes updates to subscribed entities.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class GridConnectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for polling data from a Grid Connect device."""

    def __init__(self, hass: HomeAssistant, api_client: Any) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            api_client: Your local API/client interface to the device.

        """
        super().__init__(
            hass,
            _LOGGER,
            name="Grid Connect Data Coordinator",
            update_interval=timedelta(seconds=10),
        )
        self.api_client = api_client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device/API.

        Returns:
            A dictionary with the latest data.

        Raises:
            UpdateFailed: If fetching data fails.

        """
        try:
            return await self.api_client.get_data()  # Replace with actual method
        except Exception as err:
            raise UpdateFailed(
                f"Error fetching data from Grid Connect device: {err}"
            ) from err
