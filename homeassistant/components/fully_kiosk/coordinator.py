"""Provides the The Fully Kiosk Browser DataUpdateCoordinator."""
import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from fullykiosk import FullyKiosk
from fullykiosk.exceptions import FullyKioskError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class FullyKioskDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Fully Kiosk Browser data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.fully = FullyKiosk(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            DEFAULT_PORT,
            entry.data[CONF_PASSWORD],
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.data[CONF_HOST]} deviceInfo",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            with timeout(15):
                # Get device info and settings in parallel
                result = await asyncio.gather(
                    self.fully.getDeviceInfo(), self.fully.getSettings()
                )
                # Store settings under settings key in data
                result[0]["settings"] = result[1]
                return result[0]
        except (FullyKioskError, ClientConnectorError) as error:
            raise UpdateFailed(error) from error
