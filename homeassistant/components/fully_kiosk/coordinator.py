"""Provides the Fully Kiosk Browser DataUpdateCoordinator."""

import asyncio
from typing import Any, cast

from fullykiosk import FullyKiosk
from fullykiosk.exceptions import FullyKioskError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, LOGGER, UPDATE_INTERVAL

type FullyKioskConfigEntry = ConfigEntry[FullyKioskDataUpdateCoordinator]


class FullyKioskDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Fully Kiosk Browser data."""

    config_entry: FullyKioskConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FullyKioskConfigEntry) -> None:
        """Initialize."""
        self.use_ssl = entry.data.get(CONF_SSL, False)
        self.fully = FullyKiosk(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            DEFAULT_PORT,
            entry.data[CONF_PASSWORD],
            use_ssl=self.use_ssl,
            verify_ssl=entry.data.get(CONF_VERIFY_SSL, False),
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
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
