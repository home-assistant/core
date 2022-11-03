"""Tests for the Bluetooth integration models."""
from __future__ import annotations

from unittest.mock import patch

import bleak
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
import pytest

from homeassistant.components.bluetooth.models import (
    BaseHaScanner,
    HaBleakClientWrapper,
    HaBleakScannerWrapper,
    HaBluetoothConnector,
)

from . import (
    _get_manager,
    generate_advertisement_data,
    inject_advertisement,
    inject_advertisement_with_source,
)


class MockBleakClient(BleakClient):
    """Mock bleak client."""

    def __init__(self, *args, **kwargs):
        """Mock init."""
        super().__init__(*args, **kwargs)
        self._device_path = "/dev/test"

    @property
    def is_connected(self) -> bool:
        """Mock connected."""
        return True

    async def connect(self, *args, **kwargs):
        """Mock connect."""
        return True

    async def disconnect(self, *args, **kwargs):
        """Mock disconnect."""
        pass

    async def get_services(self, *args, **kwargs):
        """Mock get_services."""
        return []


async def test_wrapped_bleak_scanner(hass, enable_bluetooth):
    """Test wrapped bleak scanner dispatches calls as expected."""
    scanner = HaBleakScannerWrapper()
    switchbot_device = BLEDevice("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
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
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )
    inject_advertisement(hass, switchbot_device, switchbot_adv)
    client = HaBleakClientWrapper(switchbot_device)
    with patch(
        "bleak.backends.bluezdbus.client.BleakClientBlueZDBus.connect"
    ) as connect:
        await client.connect()
    assert len(connect.mock_calls) == 1
    assert client._backend is not None
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()


async def test_ble_device_with_proxy_client_out_of_connections(
    hass, enable_bluetooth, one_adapter
):
    """Test we switch to the next available proxy when one runs out of connections."""
    manager = _get_manager()

    switchbot_proxy_device_no_connection_slot = BLEDevice(
        "44:44:33:11:23:45",
        "wohand",
        {
            "connector": HaBluetoothConnector(
                MockBleakClient, "mock_bleak_client", lambda: False
            ),
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
        rssi=-30,
    )
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )

    inject_advertisement_with_source(
        hass, switchbot_proxy_device_no_connection_slot, switchbot_adv, "esp32"
    )

    assert manager.async_discovered_devices(True) == [
        switchbot_proxy_device_no_connection_slot
    ]

    client = HaBleakClientWrapper(switchbot_proxy_device_no_connection_slot)
    with patch(
        "bleak.backends.bluezdbus.client.BleakClientBlueZDBus.connect"
    ), pytest.raises(BleakError):
        await client.connect()
    assert client.is_connected is False
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()


async def test_ble_device_with_proxy_client_out_of_connections_uses_best_available(
    hass, enable_bluetooth, one_adapter
):
    """Test we switch to the next available proxy when one runs out of connections."""
    manager = _get_manager()

    switchbot_proxy_device_no_connection_slot = BLEDevice(
        "44:44:33:11:23:45",
        "wohand",
        {
            "connector": HaBluetoothConnector(
                MockBleakClient, "mock_bleak_client", lambda: False
            ),
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
    )
    switchbot_proxy_device_adv_no_connection_slot = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-30,
    )
    switchbot_proxy_device_has_connection_slot = BLEDevice(
        "44:44:33:11:23:45",
        "wohand",
        {
            "connector": HaBluetoothConnector(
                MockBleakClient, "mock_bleak_client", lambda: True
            ),
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
        rssi=-40,
    )
    switchbot_proxy_device_adv_has_connection_slot = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-40,
    )
    switchbot_device = BLEDevice(
        "44:44:33:11:23:45",
        "wohand",
        {"path": "/org/bluez/hci0/dev_44_44_33_11_23_45"},
    )
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}, rssi=-100
    )

    inject_advertisement_with_source(
        hass, switchbot_device, switchbot_adv, "00:00:00:00:00:01"
    )
    inject_advertisement_with_source(
        hass,
        switchbot_proxy_device_has_connection_slot,
        switchbot_proxy_device_adv_has_connection_slot,
        "esp32_has_connection_slot",
    )
    inject_advertisement_with_source(
        hass,
        switchbot_proxy_device_no_connection_slot,
        switchbot_proxy_device_adv_no_connection_slot,
        "esp32_no_connection_slot",
    )

    class FakeScanner(BaseHaScanner):
        @property
        def discovered_devices_and_advertisement_data(
            self,
        ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
            """Return a list of discovered devices."""
            return {
                switchbot_proxy_device_has_connection_slot.address: (
                    switchbot_proxy_device_has_connection_slot,
                    switchbot_proxy_device_adv_has_connection_slot,
                )
            }

        async def async_get_device_by_address(self, address: str) -> BLEDevice | None:
            """Return a list of discovered devices."""
            if address == switchbot_proxy_device_has_connection_slot.address:
                return switchbot_proxy_device_has_connection_slot
            return None

    scanner = FakeScanner(hass, "esp32")
    cancel = manager.async_register_scanner(scanner, True)
    assert manager.async_discovered_devices(True) == [
        switchbot_proxy_device_no_connection_slot
    ]

    client = HaBleakClientWrapper(switchbot_proxy_device_no_connection_slot)
    with patch("bleak.backends.bluezdbus.client.BleakClientBlueZDBus.connect"):
        await client.connect()
    assert client.is_connected is True
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()
    cancel()


async def test_ble_device_with_proxy_client_out_of_connections_uses_best_available_macos(
    hass, enable_bluetooth, macos_adapter
):
    """Test we switch to the next available proxy when one runs out of connections on MacOS."""
    manager = _get_manager()

    switchbot_proxy_device_no_connection_slot = BLEDevice(
        "44:44:33:11:23:45",
        "wohand_no_connection_slot",
        {
            "connector": HaBluetoothConnector(
                MockBleakClient, "mock_bleak_client", lambda: False
            ),
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
        rssi=-30,
    )
    switchbot_proxy_device_no_connection_slot.metadata["delegate"] = 0
    switchbot_proxy_device_no_connection_slot_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-30,
    )
    switchbot_proxy_device_has_connection_slot = BLEDevice(
        "44:44:33:11:23:45",
        "wohand_has_connection_slot",
        {
            "connector": HaBluetoothConnector(
                MockBleakClient, "mock_bleak_client", lambda: True
            ),
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
    )
    switchbot_proxy_device_has_connection_slot.metadata["delegate"] = 0
    switchbot_proxy_device_has_connection_slot_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-40,
    )

    switchbot_device = BLEDevice(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
    switchbot_device.metadata["delegate"] = 0
    switchbot_device_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-100,
    )

    inject_advertisement_with_source(
        hass, switchbot_device, switchbot_device_adv, "00:00:00:00:00:01"
    )
    inject_advertisement_with_source(
        hass,
        switchbot_proxy_device_has_connection_slot,
        switchbot_proxy_device_has_connection_slot_adv,
        "esp32_has_connection_slot",
    )
    inject_advertisement_with_source(
        hass,
        switchbot_proxy_device_no_connection_slot,
        switchbot_proxy_device_no_connection_slot_adv,
        "esp32_no_connection_slot",
    )

    class FakeScanner(BaseHaScanner):
        @property
        def discovered_devices_and_advertisement_data(
            self,
        ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
            """Return a list of discovered devices."""
            return {
                switchbot_proxy_device_has_connection_slot.address: (
                    switchbot_proxy_device_has_connection_slot,
                    switchbot_proxy_device_has_connection_slot_adv,
                )
            }

        async def async_get_device_by_address(self, address: str) -> BLEDevice | None:
            """Return a list of discovered devices."""
            if address == switchbot_proxy_device_has_connection_slot.address:
                return switchbot_proxy_device_has_connection_slot
            return None

    scanner = FakeScanner(hass, "esp32")
    cancel = manager.async_register_scanner(scanner, True)
    assert manager.async_discovered_devices(True) == [
        switchbot_proxy_device_no_connection_slot
    ]

    client = HaBleakClientWrapper(switchbot_proxy_device_no_connection_slot)
    with patch("bleak.get_platform_client_backend_type"):
        await client.connect()
    assert client.is_connected is True
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()
    cancel()
