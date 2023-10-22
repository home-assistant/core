"""The Vevor Heater integration."""
from __future__ import annotations

import logging
from typing import Optional

from bleak import BLEDevice
from vevor_heater_ble.heater import VevorDevice

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothScanningMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vevor Heater from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    address = entry.data["address"]
    assert address is not None

    ble_device = bluetooth.async_ble_device_from_address(hass, address)

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Vevor Heater device with address {address}"
        )

    coordinator = VevorHeaterUpdateCoordinator(hass=hass, device=ble_device)

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        coordinator.set_ble_device(service_info.device)

    bluetooth.async_register_callback(
        hass,
        _async_update_ble,
        BluetoothCallbackMatcher(address=address),
        BluetoothScanningMode.ACTIVE,
    )
    return True


class VevorHeaterUpdateCoordinator(DataUpdateCoordinator[VevorDevice]):
    """Update coordinator for Vevor BLE Heaters."""

    def __init__(self, hass: HomeAssistant, device: BLEDevice) -> None:
        """Initialize the coordinator for the given BLE device. Assumes the device corresponds to a Vevor Heater."""
        self._ble_device = device
        self._vevor_device = VevorDevice(
            address=self._ble_device.address, name=self._ble_device.name
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
