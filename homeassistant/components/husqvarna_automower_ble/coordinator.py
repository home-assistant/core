"""Provides the DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from automower_ble.mower import Mower
from bleak import BleakError
from bleak_retry_connector import close_stale_connections_by_address

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


class Coordinator(DataUpdateCoordinator[dict[str, bytes]]):
    """Class to manage fetching data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        mower: Mower,
        device_info: DeviceInfo,
        address: str,
        model: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=logger,
            name="Husqvarna Automower BLE Data Update Coordinator",
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.model = model
        self.mower = mower
        self.device_info = device_info

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and any connection."""
        _LOGGER.debug("Shutdown")
        await super().async_shutdown()
        if self.mower.is_connected():
            await self.mower.disconnect()

    async def _async_find_device(self):
        _LOGGER.debug("Trying to reconnect")
        await close_stale_connections_by_address(self.address)

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if not device:
            _LOGGER.error("Can't find device")
            raise UpdateFailed("Can't find device")

        if not await self.mower.connect(device):
            raise UpdateFailed("Failed to connect")

    async def _async_update_data(self) -> dict[str, bytes]:
        """Poll the device."""
        _LOGGER.debug("Polling device")

        data: dict[str, bytes] = {}

        if not self.mower.is_connected():
            await self._async_find_device()

        try:
            data["battery_level"] = await self.mower.battery_level()
            _LOGGER.debug(data["battery_level"])
            if data["battery_level"] is None:
                await self._async_find_device()
                raise UpdateFailed("Error getting data from device")

            data["activity"] = await self.mower.mower_activity()
            _LOGGER.debug(data["activity"])
            if data["activity"] is None:
                await self._async_find_device()
                raise UpdateFailed("Error getting data from device")

            data["state"] = await self.mower.mower_state()
            _LOGGER.debug(data["state"])
            if data["state"] is None:
                await self._async_find_device()
                raise UpdateFailed("Error getting data from device")

        except BleakError as err:
            _LOGGER.error("Error getting data from device")
            await self._async_find_device()
            raise UpdateFailed("Error getting data from device") from err

        return data


class HusqvarnaAutomowerBleEntity(CoordinatorEntity[Coordinator]):
    """Coordinator entity for Husqvarna Automower Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Coordinator, context: Any = None) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator, context)
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.mower.is_connected()
