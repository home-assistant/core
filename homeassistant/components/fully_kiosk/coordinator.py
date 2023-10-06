"""Provides the Fully Kiosk Browser DataUpdateCoordinator."""
import asyncio
from typing import Any, cast

from fullykiosk import FullyKiosk
from fullykiosk.exceptions import FullyKioskError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, LOGGER, UPDATE_INTERVAL


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
            LOGGER,
            name=entry.data[CONF_HOST],
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            async with asyncio.timeout(15):
                # Get device info and settings in parallel
                result = await asyncio.gather(
                    self.fully.getDeviceInfo(), self.fully.getSettings()
                )
                # Store settings under settings key in data
                result[0]["settings"] = result[1]
                return cast(dict[str, Any], result[0])
        except FullyKioskError as error:
            raise UpdateFailed(error) from error
