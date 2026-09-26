"""Home Assistant-backed Bluetooth adapter for the pywybot BLE client.

Implements pywybot's ``BluetoothAdapter`` protocol on top of Home Assistant's
Bluetooth stack so the library can discover and resolve WyBot BLE devices
without depending on Home Assistant itself.
"""

from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
    async_scanner_count,
)
from homeassistant.core import HomeAssistant


class HomeAssistantBluetoothAdapter:
    """Supply BLE discovery to pywybot using Home Assistant's Bluetooth stack."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the adapter with a Home Assistant instance."""
        self._hass = hass

    def scanner_count(self) -> int:
        """Return the number of active connectable BLE scanners."""
        return async_scanner_count(self._hass, connectable=True)

    def discovered_devices(self) -> list[BLEDevice]:
        """Return the currently discovered connectable BLE devices."""
        return [
            info.device
            for info in async_discovered_service_info(self._hass, connectable=True)
        ]

    def device_from_address(self, address: str) -> BLEDevice | None:
        """Resolve a connectable BLEDevice for ``address``, or None."""
        return async_ble_device_from_address(self._hass, address, connectable=True)
