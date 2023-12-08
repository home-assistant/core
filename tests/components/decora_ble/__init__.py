"""Tests for the Decora BLE integration."""

from unittest.mock import MagicMock, patch

from decora_bleak import DECORA_SERVICE_UUID

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.decora_ble.async_setup_entry",
        return_value=return_value,
    )


def patch_async_ble_device_from_address(return_value: BluetoothServiceInfoBleak | None):
    """Patch async ble device from address to return a given value."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=return_value,
    )


def patch_decora_ble_get_api_key(return_value: str):
    """Patch Decora BLE api key call to return a given value."""
    return patch(
        "decora_bleak.DecoraBLEDevice.get_api_key",
        return_value=return_value,
    )


def patch_decora_ble_get_api_key_fail_with_exception(ex):
    """Patch Decora BLE api key call to raise an exception."""
    return patch(
        "decora_bleak.DecoraBLEDevice.get_api_key",
        MagicMock(side_effect=ex),
    )


def patch_decora_ble_connect_success():
    """Patch Decora BLE connect call to return a given value."""
    return patch(
        "decora_bleak.DecoraBLEDevice.connect",
        return_value=None,
    )


def patch_decora_ble_connect_fail_with_exception(ex):
    """Patch Decora BLE connect call to raise an exception."""
    return patch(
        "decora_bleak.DecoraBLEDevice.connect",
        MagicMock(side_effect=ex),
    )


DECORA_BLE_SERVICE_INFO = BluetoothServiceInfo(
    name="Leviton DD710 v6.4",
    address="11:22:33:44:55:66",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[DECORA_SERVICE_UUID],
    service_data={},
    source="local",
)


NOT_DECORA_BLE_SERVICE_INFO = BluetoothServiceInfo(
    name="Neviton",
    address="11:22:33:44:55:66",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
)
