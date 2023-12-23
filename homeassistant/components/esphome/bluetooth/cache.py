"""Bluetooth cache for esphome."""
from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field

from bleak.backends.service import BleakGATTServiceCollection
from lru import LRU  # pylint: disable=no-name-in-module

MAX_CACHED_SERVICES = 128


@dataclass(slots=True)
class ESPHomeBluetoothCache:
    """Shared cache between all ESPHome bluetooth devices."""

    _gatt_services_cache: MutableMapping[int, BleakGATTServiceCollection] = field(
        default_factory=lambda: LRU(MAX_CACHED_SERVICES)
    )
    _gatt_mtu_cache: MutableMapping[int, int] = field(
        default_factory=lambda: LRU(MAX_CACHED_SERVICES)
    )

    def get_gatt_services_cache(
        self, address: int
    ) -> BleakGATTServiceCollection | None:
        """Get the BleakGATTServiceCollection for the given address."""
        return self._gatt_services_cache.get(address)

    def set_gatt_services_cache(
        self, address: int, services: BleakGATTServiceCollection
    ) -> None:
        """Set the BleakGATTServiceCollection for the given address."""
        self._gatt_services_cache[address] = services

    def clear_gatt_services_cache(self, address: int) -> None:
        """Clear the BleakGATTServiceCollection for the given address."""
        self._gatt_services_cache.pop(address, None)

    def get_gatt_mtu_cache(self, address: int) -> int | None:
        """Get the mtu cache for the given address."""
        return self._gatt_mtu_cache.get(address)

    def set_gatt_mtu_cache(self, address: int, mtu: int) -> None:
        """Set the mtu cache for the given address."""
        self._gatt_mtu_cache[address] = mtu

    def clear_gatt_mtu_cache(self, address: int) -> None:
        """Clear the mtu cache for the given address."""
        self._gatt_mtu_cache.pop(address, None)
