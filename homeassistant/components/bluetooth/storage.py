"""Storage for remote scanners."""
from __future__ import annotations

from bluetooth_adapters import (
    DiscoveredDeviceAdvertisementData,
    DiscoveredDeviceAdvertisementDataDict,
    DiscoveryStorageType,
    discovered_device_advertisement_data_from_dict,
    discovered_device_advertisement_data_to_dict,
    expire_stale_scanner_discovered_device_advertisement_data,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

REMOTE_SCANNER_STORAGE_VERSION = 1
REMOTE_SCANNER_STORAGE_KEY = "bluetooth.remote_scanners"
SCANNER_SAVE_DELAY = 5


class BluetoothStorage:
    """Storage for remote scanners."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the storage."""
        self._store: Store[DiscoveryStorageType] = Store(
            hass, REMOTE_SCANNER_STORAGE_VERSION, REMOTE_SCANNER_STORAGE_KEY
        )
        self._data: DiscoveryStorageType = {}

    async def async_setup(self) -> None:
        """Set up the storage."""
        self._data = await self._store.async_load() or {}
        expire_stale_scanner_discovered_device_advertisement_data(self._data)

    def scanners(self) -> list[str]:
        """Get all scanners."""
        return list(self._data.keys())

    @callback
    def async_get_advertisement_history(
        self, scanner: str
    ) -> DiscoveredDeviceAdvertisementData | None:
        """Get discovered devices by scanner."""
        if not (scanner_data := self._data.get(scanner)):
            return None
        return discovered_device_advertisement_data_from_dict(scanner_data)

    @callback
    def async_get_advertisement_history_as_dict(
        self, scanner: str
    ) -> DiscoveredDeviceAdvertisementDataDict | None:
        """Get discovered devices by scanner as a dict."""
        return self._data.get(scanner)

    @callback
    def _async_get_data(self) -> DiscoveryStorageType:
        """Get data to save to disk."""
        return self._data

    @callback
    def async_set_advertisement_history(
        self, scanner: str, data: DiscoveredDeviceAdvertisementData
    ) -> None:
        """Set discovered devices by scanner."""
        self._data[scanner] = discovered_device_advertisement_data_to_dict(data)
        self._store.async_delay_save(self._async_get_data, SCANNER_SAVE_DELAY)
