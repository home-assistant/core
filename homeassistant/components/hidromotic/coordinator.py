"""DataUpdateCoordinator for Hidromotic."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

from pyhidromotic import HidromoticClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, INITIAL_DATA_WAIT_SECONDS

_LOGGER = logging.getLogger(__name__)


class HidromoticCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Hidromotic device."""

    def __init__(
        self, hass: HomeAssistant, client: HidromoticClient, config_entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # We use push updates via WebSocket
            config_entry=config_entry,
        )
        self.client = client
        self._remove_callback: Callable[[], None] | None = None

    async def async_setup(self) -> bool:
        """Set up the coordinator."""
        # Register callback for data updates
        self._remove_callback = self.client.register_callback(self._on_data_update)

        # Connect to device
        if not await self.client.connect():
            return False

        # Wait for initial data
        await asyncio.sleep(INITIAL_DATA_WAIT_SECONDS)

        # Set initial data
        self.async_set_updated_data(self.client.data)
        return True

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._remove_callback:
            self._remove_callback()
        await self.client.disconnect()

    @callback
    def _on_data_update(self, data: dict[str, Any]) -> None:
        """Handle data update from WebSocket."""
        self.async_set_updated_data(data)

    async def async_set_zone_state(self, zone_id: int, on: bool) -> None:
        """Set zone state."""
        await self.client.set_zone_state(zone_id, on)

    async def async_set_tank_state(self, tank_id: int, on: bool) -> None:
        """Set tank state."""
        await self.client.set_tank_state(tank_id, on)

    async def async_refresh_data(self) -> None:
        """Request data refresh from device."""
        await self.client.refresh()

    def get_zones(self) -> dict[int, dict[str, Any]]:
        """Get all zones."""
        return self.client.get_zones()

    def get_tanks(self) -> dict[int, dict[str, Any]]:
        """Get all tanks."""
        return self.client.get_tanks()

    def get_pump(self) -> dict[str, Any]:
        """Get pump status."""
        return self.client.get_pump()
