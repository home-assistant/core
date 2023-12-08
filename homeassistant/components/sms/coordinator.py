"""DataUpdateCoordinators for the sms integration."""
import asyncio
from datetime import timedelta
import logging

import gammu

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SignalCoordinator(DataUpdateCoordinator):
    """Signal strength coordinator."""

    def __init__(self, hass, gateway):
        """Initialize signal strength coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Device signal state",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._gateway = gateway

    async def _async_update_data(self):
        """Fetch device signal quality."""
        try:
            async with asyncio.timeout(10):
                return await self._gateway.get_signal_quality_async()
        except gammu.GSMError as exc:
            raise UpdateFailed(f"Error communicating with device: {exc}") from exc


class NetworkCoordinator(DataUpdateCoordinator):
    """Network info coordinator."""

    def __init__(self, hass, gateway):
        """Initialize network info coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Device network state",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._gateway = gateway

    async def _async_update_data(self):
        """Fetch device network info."""
        try:
            async with asyncio.timeout(10):
                return await self._gateway.get_network_info_async()
        except gammu.GSMError as exc:
            raise UpdateFailed(f"Error communicating with device: {exc}") from exc
