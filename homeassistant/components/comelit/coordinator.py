"""Support for Comelit."""
import asyncio
from datetime import timedelta
from typing import Any

from aiocomelit import (
    ComeliteSerialBridgeAPi,
)
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN


class ComelitSerialBridge(DataUpdateCoordinator):
    """Queries Comelit Serial Bridge."""

    def __init__(self, hass: HomeAssistant, host: str, pin: int) -> None:
        """Initialize the scanner."""

        self._host = host
        self._pin = pin

        self.api = ComeliteSerialBridgeAPi(host, pin)

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update router data."""
        _LOGGER.debug("Polling Comelit Serial Bridge host: %s", self._host)
        try:
            logged = await self.api.login()
        except (asyncio.exceptions.TimeoutError, aiohttp.ClientConnectorError) as err:
            _LOGGER.warning("Connection error for %s", self._host)
            raise UpdateFailed(f"Error fetching data: {repr(err)}") from err

        if not logged:
            raise ConfigEntryAuthFailed

        devices_data = await self.api.get_all_devices()
        alarm_data = await self.api.get_alarm_config()
        await self.api.logout()

        return devices_data | alarm_data
