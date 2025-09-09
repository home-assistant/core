"""The Medcom BLE integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from bleak import BleakError
from medcom_ble import MedcomBleDevice, MedcomBleDeviceData

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MedcomBleUpdateCoordinator(DataUpdateCoordinator[MedcomBleDevice]):
    """Coordinator for Medcom BLE radiation monitor data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, address: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._address = address
        self._elevation = hass.config.elevation
        self._is_metric = hass.config.units is METRIC_SYSTEM

    async def _async_update_data(self) -> MedcomBleDevice:
        """Get data from Medcom BLE radiation monitor."""
        ble_device = bluetooth.async_ble_device_from_address(self.hass, self._address)
        inspector = MedcomBleDeviceData(_LOGGER, self._elevation, self._is_metric)

        try:
            data = await inspector.update_device(ble_device)
        except BleakError as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

        return data
