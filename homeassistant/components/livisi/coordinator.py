"""Code to manage fetching LIVISI data API."""
from datetime import timedelta
from typing import Any

from aiolivisi import AioLivisi

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEVICE_POLLING_DELAY, LOGGER


class LivisiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching LIVISI data API."""

    def __init__(self, hass: HomeAssistant, aiolivisi: AioLivisi) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Livisi devices",
            update_interval=timedelta(seconds=DEVICE_POLLING_DELAY),
        )
        self.hass = hass
        self.aiolivisi = aiolivisi

    async def _async_update_data(self):
        """Set device list."""
        return await self.async_get_devices()

    async def async_get_devices(self) -> list:
        """Set the discovered devices list."""
        shc_devices = await self.aiolivisi.async_get_devices()
        if bool(shc_devices) is False:
            shc_devices = await self.aiolivisi.async_get_devices()
        return shc_devices
