"""Data update coordinators for Vevor BLE Heater integration."""

import logging
from typing import Optional

from bleak import BLEDevice
import bluetooth_data_tools
from vevor_heater_ble.heater import VevorDevice

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class VevorHeaterUpdateCoordinator(DataUpdateCoordinator[VevorDevice]):
    """Update coordinator for Vevor BLE Heaters."""

    def __init__(self, hass: HomeAssistant, device: BLEDevice) -> None:
        """Initialize the coordinator for the given BLE device. Assumes the device corresponds to a Vevor Heater."""
        self._ble_device = device
        address = self._ble_device.address
        name = self._ble_device.name or bluetooth_data_tools.short_address(address)
        self._vevor_device = VevorDevice(
            address=address,
            name=f"Vevor {name}",
        )
        super().__init__(
            hass, logger=_LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )

    async def _async_update_data(self):
        """Attempt to update the sensor data."""
        try:
            await self._vevor_device.refresh_status(self._ble_device)
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

        return self._vevor_device

    def get_device_name(self) -> Optional[str]:
        """Return the Bluetooth name of the associated heater."""
        return self._ble_device.name

    def get_device_address(self) -> str:
        """Return the Bluetooth address of the associated heater."""
        return self._ble_device.address

    def set_ble_device(self, device: BLEDevice):
        """Set the associated Bluetooth device. Only used internally in BT device update listener."""
        self._ble_device = device

    async def turn_on(self):
        """Turn the associated heater on."""
        await self._vevor_device.turn_on(self._ble_device)

    async def turn_off(self):
        """Turn the associated heater off."""
        await self._vevor_device.turn_off(self._ble_device)

    async def set_target_temperature(self, temperature: int):
        """Set the target room temperature."""
        await self._vevor_device.set_target_temperature(self._ble_device, temperature)

    async def set_target_power_level(self, power_level: int):
        """Set the power level for the heater."""
        await self._vevor_device.set_target_power_level(self._ble_device, power_level)
