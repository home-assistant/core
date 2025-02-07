"""Coordinator for the Lektrico Charging Station integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from lektricowifi import Device, DeviceConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_HW_VERSION,
    ATTR_SERIAL_NUMBER,
    CONF_HOST,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

SCAN_INTERVAL = timedelta(seconds=10)


class LektricoDeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for Lektrico device."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, device_name: str) -> None:
        """Initialize a Lektrico Device."""
        super().__init__(
            hass,
            LOGGER,
            name=device_name,
            update_interval=SCAN_INTERVAL,
        )
        self.device = Device(
            self.config_entry.data[CONF_HOST],
            asyncClient=get_async_client(hass),
        )
        self.serial_number: str = self.config_entry.data[ATTR_SERIAL_NUMBER]
        self.board_revision: str = self.config_entry.data[ATTR_HW_VERSION]
        self.device_type: str = self.config_entry.data[CONF_TYPE]

    async def _async_update_data(self) -> dict[str, Any]:
        """Async Update device state."""
        try:
            return await self.device.device_info(self.device_type)
        except DeviceConnectionError as lek_ex:
            raise UpdateFailed(lek_ex) from lek_ex
