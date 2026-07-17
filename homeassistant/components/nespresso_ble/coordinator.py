"""Coordinator for the Nespresso Vertuo integration."""

from datetime import timedelta
import logging
from typing import override

from bleak import BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import close_stale_connections_by_address
from nespresso_ble import NespressoError, VMiniBluetoothDeviceData, VMiniDevice

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type NespressoBLEConfigEntry = ConfigEntry[NespressoBLECoordinator]


class NespressoBLECoordinator(DataUpdateCoordinator[VMiniDevice]):
    """Coordinator to fetch data from a Nespresso Vertuo machine over BLE."""

    ble_device: BLEDevice
    config_entry: NespressoBLEConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NespressoBLEConfigEntry) -> None:
        """Initialize the coordinator."""
        self._client = VMiniBluetoothDeviceData(_LOGGER)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @override
    async def _async_setup(self) -> None:
        """Resolve the BLE device and clean stale connections."""
        address = self.config_entry.unique_id
        assert address is not None
        await close_stale_connections_by_address(address)

    def _async_get_ble_device(self) -> BLEDevice:
        """Return a fresh BLE device for the configured address."""
        address = self.config_entry.unique_id
        assert address is not None
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, address, connectable=True
        )
        if ble_device is None:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={
                    "address": address,
                    "reason": bluetooth.async_address_reachability_diagnostics(
                        self.hass,
                        address.upper(),
                        BluetoothReachabilityIntent.CONNECTION,
                    ),
                },
            )
        return ble_device

    @override
    async def _async_update_data(self) -> VMiniDevice:
        """Fetch the latest data from the machine."""
        ble_device = self._async_get_ble_device()
        try:
            return await self._client.update_device(ble_device)
        except (BleakError, NespressoError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
