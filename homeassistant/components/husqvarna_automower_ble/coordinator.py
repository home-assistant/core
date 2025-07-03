"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING

from automower_ble.mower import Mower
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import HusqvarnaConfigEntry

SCAN_INTERVAL = timedelta(seconds=60)


class HusqvarnaCoordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Class to manage fetching data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HusqvarnaConfigEntry,
        mower: Mower,
        address: str,
        channel_id: str,
        model: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.channel_id = channel_id
        self.model = model
        self.mower = mower
        self.lock = asyncio.Lock()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        LOGGER.debug("Shutdown")
        await super().async_shutdown()
        async with self.lock:
            if self.mower.is_connected():
                await self.mower.disconnect()

    async def async_keep_alive(self, dt) -> None:
        """Send a keep alive to the mower."""
        async with self.lock:
            if not self.mower.is_connected():
                return

            LOGGER.debug("Sending keep alive")
            try:
                await self.mower.command("KeepAlive")
            except BleakError as err:
                LOGGER.warning("Failed to send keep alive: %s", err)

    async def _async_find_device(self):
        async with self.lock:
            if self.mower.is_connected():
                return

            LOGGER.debug("Trying to reconnect")
            await close_stale_connections_by_address(self.address)

            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )

            try:
                if not await self.mower.connect(device):
                    raise UpdateFailed("Failed to connect")
            except BleakError as err:
                raise UpdateFailed("Failed to connect") from err

    async def _async_update_data(self) -> dict[str, bytes]:
        """Poll the device."""
        LOGGER.debug("Polling device")

        data: dict[str, bytes] = {}

        await self._async_find_device()

        try:
            async with self.lock:
                data["battery_level"] = await self.mower.battery_level()
                data["activity"] = await self.mower.mower_activity()
                data["state"] = await self.mower.mower_state()

            LOGGER.debug(data)

            for key, value in data.items():
                if value is None:
                    await self._async_find_device()
                    raise UpdateFailed(f"Error getting data from device: {key} is None")

        except BleakError as err:
            LOGGER.error("Error getting data from device")
            await self._async_find_device()
            raise UpdateFailed("Error getting data from device") from err

        return data
