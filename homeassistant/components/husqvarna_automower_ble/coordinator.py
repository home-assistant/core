"""Provides the DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from automower_ble.mower import Mower

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
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

    async def _async_update_data(self) -> dict[str, bytes]:
        """Poll the device."""
        _LOGGER.debug("Polling device")

        data: dict[str, bytes] = {}

        if await self.mower.is_connected():
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if await self.mower.connect(device) == False:
                return

        data["battery_level"] = await self.mower.battery_level()
        _LOGGER.debug(data["battery_level"])
        data["activity"] = await self.mower.mower_activity()
        _LOGGER.debug(data["activity"])
        data["state"] = await self.mower.mower_state()
        _LOGGER.debug(data["state"])

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
