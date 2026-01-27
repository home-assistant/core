"""The StoveData update coordination."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from pystove import DATA_FIRMWARE_VERSION, Stove

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class StoveDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage the polling of the Airbox API."""

    def __init__(
        self,
        hass: HomeAssistant,
        stove: Stove,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.stove = stove

    async def _async_setup(self):
        pass

    async def _async_update_data(self):
        async with asyncio.timeout(1):
            return await self.stove.get_data()

    @property
    def api(self) -> Stove:
        """The Stove API."""
        return self.stove

    @property
    def device_id(self) -> str:
        """The stoves unique device ID."""
        if self.stove.stove_mdns is None:
            # fallback as not every FW provides this info
            return self.stove.stove_ip
        return self.stove.stove_mdns

    def device_info(self):
        """Generate common device info for entities."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=self.stove.name,
            manufacturer="HWAM",
            model=self.stove.series,
            model_id=self.stove.series,
            sw_version=self.data[DATA_FIRMWARE_VERSION],
        )
