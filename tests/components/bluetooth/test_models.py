"""Tests for the Bluetooth integration models."""


import bleak
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
import pytest

from homeassistant.components.bluetooth.models import (
    HaBleakClientWrapper,
    HaBleakScannerWrapper,
)

from . import inject_advertisement


async def test_wrapped_bleak_scanner(hass, enable_bluetooth):
    """Test wrapped bleak scanner dispatches calls as expected."""
    scanner = HaBleakScannerWrapper()
    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    switchbot_adv = AdvertisementData(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )
    inject_advertisement(hass, switchbot_device, switchbot_adv)
    assert scanner.discovered_devices == [switchbot_device]
    assert await scanner.discover() == [switchbot_device]


async def test_wrapped_bleak_client_raises_device_missing(hass, enable_bluetooth):
    """Test wrapped bleak client dispatches calls as expected."""
    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    client = HaBleakClientWrapper(switchbot_device)
    assert client.is_connected is False
    with pytest.raises(bleak.BleakError):
        await client.connect()
    assert client.is_connected is False
    await client.disconnect()


async def test_wrapped_bleak_client_set_disconnected_callback_before_connected(
    hass, enable_bluetooth
):
    """Test wrapped bleak client can set a disconnected callback before connected."""
    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    client = HaBleakClientWrapper(switchbot_device)
    client.set_disconnected_callback(lambda client: None)


async def test_wrapped_bleak_client_set_disconnected_callback_after_connected(
    hass, enable_bluetooth, one_adapter
):
    """Test wrapped bleak client can set a disconnected callback after connected."""
    switchbot_device = BLEDevice(
        "44:44:33:11:23:45", "wohand", {"path": "/org/bluez/hci0/dev_44_44_33_11_23_45"}
    )
    switchbot_adv = AdvertisementData(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )
    inject_advertisement(hass, switchbot_device, switchbot_adv)
    client = HaBleakClientWrapper(switchbot_device)
    await client.connect()
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()
