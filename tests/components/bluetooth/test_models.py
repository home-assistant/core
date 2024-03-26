"""Tests for the Bluetooth integration models."""

from __future__ import annotations

from unittest.mock import patch

import bleak
from bleak import BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from habluetooth.wrappers import HaBleakClientWrapper, HaBleakScannerWrapper
import pytest

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BaseHaScanner,
    HaBluetoothConnector,
)
from homeassistant.core import HomeAssistant

from . import (
    FakeScannerMixin,
    MockBleakClient,
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement,
    inject_advertisement_with_source,
)


async def test_wrapped_bleak_scanner(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test wrapped bleak scanner dispatches calls as expected."""
    scanner = HaBleakScannerWrapper()
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )
    inject_advertisement(hass, switchbot_device, switchbot_adv)
    assert scanner.discovered_devices == [switchbot_device]
    assert await scanner.discover() == [switchbot_device]


async def test_wrapped_bleak_client_raises_device_missing(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test wrapped bleak client dispatches calls as expected."""
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    client = HaBleakClientWrapper(switchbot_device)
    assert client.is_connected is False
    with pytest.raises(bleak.BleakError):
        await client.connect()
    assert client.is_connected is False
    await client.disconnect()
    assert await client.clear_cache() is False


async def test_wrapped_bleak_client_set_disconnected_callback_before_connected(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test wrapped bleak client can set a disconnected callback before connected."""
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    client = HaBleakClientWrapper(switchbot_device)
    client.set_disconnected_callback(lambda client: None)


async def test_wrapped_bleak_client_local_adapter_only(
    hass: HomeAssistant, enable_bluetooth: None, one_adapter: None
) -> None:
    """Test wrapped bleak client with only a local adapter."""
    manager = _get_manager()

    switchbot_device = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {"path": "/org/bluez/hci0/dev_44_44_33_11_23_45"},
    )
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}, rssi=-100
    )

    class FakeScanner(FakeScannerMixin, BaseHaScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return a list of discovered devices."""
            return []

        @property
        def discovered_devices_and_advertisement_data(
            self,
        ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
            """Return a list of discovered devices."""
            return {
                switchbot_device.address: (
                    switchbot_device,
                    switchbot_adv,
                )
            }

        async def async_get_device_by_address(self, address: str) -> BLEDevice | None:
            """Return a list of discovered devices."""
            if address == switchbot_device.address:
                return switchbot_adv
            return None

    scanner = FakeScanner(
        "00:00:00:00:00:01",
        "hci0",
    )
    scanner.connectable = True
    cancel = manager.async_register_scanner(scanner)
    inject_advertisement_with_source(
        hass, switchbot_device, switchbot_adv, "00:00:00:00:00:01"
    )

    client = HaBleakClientWrapper(switchbot_device)
    with (
        patch(
            "bleak.backends.bluezdbus.client.BleakClientBlueZDBus.connect",
            return_value=True,
        ),
        patch(
            "bleak.backends.bluezdbus.client.BleakClientBlueZDBus.is_connected", True
        ),
    ):
        assert await client.connect() is True
        assert client.is_connected is True
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()
    cancel()


async def test_wrapped_bleak_client_set_disconnected_callback_after_connected(
    hass: HomeAssistant, enable_bluetooth: None, one_adapter: None
) -> None:
    """Test wrapped bleak client can set a disconnected callback after connected."""
    manager = _get_manager()

    switchbot_proxy_device_has_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {
            "source": "esp32_has_connection_slot",
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
    switchbot_device = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {"path": "/org/bluez/hci0/dev_44_44_33_11_23_45"},
    )
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}, rssi=-100
    )

    class FakeScanner(FakeScannerMixin, BaseHaRemoteScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return a list of discovered devices."""
            return []

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

    connector = HaBluetoothConnector(
        MockBleakClient, "esp32_has_connection_slot", lambda: True
    )
    scanner = FakeScanner(
        "esp32_has_connection_slot",
        "esp32_has_connection_slot",
        connector,
        True,
    )
    cancel = manager.async_register_scanner(scanner)
    inject_advertisement_with_source(
        hass, switchbot_device, switchbot_adv, "00:00:00:00:00:01"
    )
    inject_advertisement_with_source(
        hass,
        switchbot_proxy_device_has_connection_slot,
        switchbot_proxy_device_adv_has_connection_slot,
        "esp32_has_connection_slot",
    )
    client = HaBleakClientWrapper(switchbot_proxy_device_has_connection_slot)
    with (
        patch(
            "bleak.backends.bluezdbus.client.BleakClientBlueZDBus.connect",
            return_value=True,
        ),
        patch(
            "bleak.backends.bluezdbus.client.BleakClientBlueZDBus.is_connected", True
        ),
    ):
        assert await client.connect() is True
        assert client.is_connected is True
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()
    cancel()


async def test_ble_device_with_proxy_client_out_of_connections_no_scanners(
    hass: HomeAssistant, enable_bluetooth: None, one_adapter: None
) -> None:
    """Test we switch to the next available proxy when one runs out of connections with no scanners."""
    manager = _get_manager()

    switchbot_proxy_device_no_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {
            "source": "esp32",
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
    with (
        patch("bleak.backends.bluezdbus.client.BleakClientBlueZDBus.connect"),
        pytest.raises(BleakError),
    ):
        await client.connect()
    assert client.is_connected is False
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()


async def test_ble_device_with_proxy_client_out_of_connections(
    hass: HomeAssistant, enable_bluetooth: None, one_adapter: None
) -> None:
    """Test handling all scanners are out of connection slots."""
    manager = _get_manager()

    switchbot_proxy_device_no_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {
            "source": "esp32",
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
        rssi=-30,
    )
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )

    class FakeScanner(FakeScannerMixin, BaseHaRemoteScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return a list of discovered devices."""
            return []

        @property
        def discovered_devices_and_advertisement_data(
            self,
        ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
            """Return a list of discovered devices."""
            return {
                switchbot_proxy_device_no_connection_slot.address: (
                    switchbot_proxy_device_no_connection_slot,
                    switchbot_adv,
                )
            }

        async def async_get_device_by_address(self, address: str) -> BLEDevice | None:
            """Return a list of discovered devices."""
            if address == switchbot_proxy_device_no_connection_slot.address:
                return switchbot_adv
            return None

    connector = HaBluetoothConnector(MockBleakClient, "esp32", lambda: False)
    scanner = FakeScanner("esp32", "esp32", connector, True)
    cancel = manager.async_register_scanner(scanner)
    inject_advertisement_with_source(
        hass, switchbot_proxy_device_no_connection_slot, switchbot_adv, "esp32"
    )

    assert manager.async_discovered_devices(True) == [
        switchbot_proxy_device_no_connection_slot
    ]

    client = HaBleakClientWrapper(switchbot_proxy_device_no_connection_slot)
    with (
        patch("bleak.backends.bluezdbus.client.BleakClientBlueZDBus.connect"),
        pytest.raises(BleakError),
    ):
        await client.connect()
    assert client.is_connected is False
    client.set_disconnected_callback(lambda client: None)
    await client.disconnect()
    cancel()


async def test_ble_device_with_proxy_clear_cache(
    hass: HomeAssistant, enable_bluetooth: None, one_adapter: None
) -> None:
    """Test we can clear cache on the proxy."""
    manager = _get_manager()

    switchbot_proxy_device_with_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {
            "source": "esp32",
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
        rssi=-30,
    )
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )

    class FakeScanner(FakeScannerMixin, BaseHaRemoteScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return a list of discovered devices."""
            return []

        @property
        def discovered_devices_and_advertisement_data(
            self,
        ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
            """Return a list of discovered devices."""
            return {
                switchbot_proxy_device_with_connection_slot.address: (
                    switchbot_proxy_device_with_connection_slot,
                    switchbot_adv,
                )
            }

        async def async_get_device_by_address(self, address: str) -> BLEDevice | None:
            """Return a list of discovered devices."""
            if address == switchbot_proxy_device_with_connection_slot.address:
                return switchbot_adv
            return None

    connector = HaBluetoothConnector(MockBleakClient, "esp32", lambda: True)
    scanner = FakeScanner("esp32", "esp32", connector, True)
    cancel = manager.async_register_scanner(scanner)
    inject_advertisement_with_source(
        hass, switchbot_proxy_device_with_connection_slot, switchbot_adv, "esp32"
    )

    assert manager.async_discovered_devices(True) == [
        switchbot_proxy_device_with_connection_slot
    ]

    client = HaBleakClientWrapper(switchbot_proxy_device_with_connection_slot)
    await client.connect()
    assert client.is_connected is True
    assert await client.clear_cache() is True
    await client.disconnect()
    cancel()


async def test_ble_device_with_proxy_client_out_of_connections_uses_best_available(
    hass: HomeAssistant, enable_bluetooth: None, one_adapter: None
) -> None:
    """Test we switch to the next available proxy when one runs out of connections."""
    manager = _get_manager()

    switchbot_proxy_device_no_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {
            "source": "esp32_no_connection_slot",
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
    )
    switchbot_proxy_device_adv_no_connection_slot = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-30,
    )
    switchbot_proxy_device_has_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {
            "source": "esp32_has_connection_slot",
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
    switchbot_device = generate_ble_device(
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

    class FakeScanner(FakeScannerMixin, BaseHaRemoteScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return a list of discovered devices."""
            return []

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

    connector = HaBluetoothConnector(
        MockBleakClient, "esp32_has_connection_slot", lambda: True
    )
    scanner = FakeScanner(
        "esp32_has_connection_slot",
        "esp32_has_connection_slot",
        connector,
        True,
    )
    cancel = manager.async_register_scanner(scanner)
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
    hass: HomeAssistant, enable_bluetooth: None, macos_adapter: None
) -> None:
    """Test we switch to the next available proxy when one runs out of connections on MacOS."""
    manager = _get_manager()

    switchbot_proxy_device_no_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand_no_connection_slot",
        {
            "source": "esp32_no_connection_slot",
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
        rssi=-30,
    )
    switchbot_proxy_device_no_connection_slot_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-30,
    )
    switchbot_proxy_device_has_connection_slot = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand_has_connection_slot",
        {
            "source": "esp32_has_connection_slot",
            "path": "/org/bluez/hci0/dev_44_44_33_11_23_45",
        },
    )
    switchbot_proxy_device_has_connection_slot_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-40,
    )

    switchbot_device = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
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

    class FakeScanner(FakeScannerMixin, BaseHaRemoteScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return a list of discovered devices."""
            return []

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

    connector = HaBluetoothConnector(
        MockBleakClient, "esp32_has_connection_slot", lambda: True
    )
    scanner = FakeScanner(
        "esp32_has_connection_slot",
        "esp32_has_connection_slot",
        connector,
        True,
    )
    cancel = manager.async_register_scanner(scanner)
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
