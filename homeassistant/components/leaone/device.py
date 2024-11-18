"""Support for Leaone devices."""

from __future__ import annotations

from leaone_ble import DeviceKey

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothEntityKey,
)


def device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)
