"""Tests for the Bluetooth integration API."""

import time

from bleak.backends.scanner import AdvertisementData, BLEDevice
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BaseHaRemoteScanner,
    HaBluetoothConnector,
    async_scanner_by_source,
    async_scanner_devices_by_address,
)
from homeassistant.core import HomeAssistant

from . import (
    FakeScanner,
    MockBleakClient,
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
)


@pytest.mark.usefixtures("enable_bluetooth")
async def test_scanner_by_source(hass: HomeAssistant) -> None:
    """Test we can get a scanner by source."""

    hci2_scanner = FakeScanner("hci2", "hci2")
    cancel_hci2 = bluetooth.async_register_scanner(hass, hci2_scanner)

    assert async_scanner_by_source(hass, "hci2") is hci2_scanner
    cancel_hci2()
    assert async_scanner_by_source(hass, "hci2") is None


async def test_monotonic_time() -> None:
    """Test monotonic time."""
    assert MONOTONIC_TIME() == pytest.approx(time.monotonic(), abs=0.1)


@pytest.mark.usefixtures("enable_bluetooth")
async def test_async_get_advertisement_callback(hass: HomeAssistant) -> None:
    """Test getting advertisement callback."""
    callback = bluetooth.async_get_advertisement_callback(hass)
    assert callback is not None


@pytest.mark.usefixtures("enable_bluetooth")
async def test_async_scanner_devices_by_address_connectable(
    hass: HomeAssistant,
) -> None:
    """Test getting scanner devices by address with connectable devices."""
    manager = _get_manager()

    class FakeInjectableScanner(BaseHaRemoteScanner):
        def inject_advertisement(
            self, device: BLEDevice, advertisement_data: AdvertisementData
        ) -> None:
            """Inject an advertisement."""
            self._async_on_advertisement(
                device.address,
                advertisement_data.rssi,
                device.name,
                advertisement_data.service_uuids,
                advertisement_data.service_data,
                advertisement_data.manufacturer_data,
                advertisement_data.tx_power,
                {"scanner_specific_data": "test"},
                MONOTONIC_TIME(),
            )

    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeInjectableScanner("esp32", "esp32", connector, True)
    unsetup = scanner.async_setup()
    cancel = manager.async_register_scanner(scanner)
    switchbot_device = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
    switchbot_device_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["050a021a-0000-1000-8000-00805f9b34fb"],
        service_data={"050a021a-0000-1000-8000-00805f9b34fb": b"\n\xff"},
        manufacturer_data={1: b"\x01"},
        rssi=-100,
    )
    scanner.inject_advertisement(switchbot_device, switchbot_device_adv)
    assert async_scanner_devices_by_address(
        hass, switchbot_device.address, connectable=True
    ) == async_scanner_devices_by_address(hass, "44:44:33:11:23:45", connectable=False)
    devices = async_scanner_devices_by_address(
        hass, switchbot_device.address, connectable=False
    )
    assert len(devices) == 1
    assert devices[0].scanner == scanner
    assert devices[0].ble_device.name == switchbot_device.name
    assert devices[0].advertisement.local_name == switchbot_device_adv.local_name
    unsetup()
    cancel()


@pytest.mark.usefixtures("enable_bluetooth")
async def test_async_scanner_devices_by_address_non_connectable(
    hass: HomeAssistant,
) -> None:
    """Test getting scanner devices by address with non-connectable devices."""
    manager = _get_manager()
    switchbot_device = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
    switchbot_device_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["050a021a-0000-1000-8000-00805f9b34fb"],
        service_data={"050a021a-0000-1000-8000-00805f9b34fb": b"\n\xff"},
        manufacturer_data={1: b"\x01"},
        rssi=-100,
    )

    class FakeStaticScanner(FakeScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            """Return a list of discovered devices."""
            return [switchbot_device]

        @property
        def discovered_devices_and_advertisement_data(
            self,
        ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
            """Return a list of discovered devices and their advertisement data."""
            return {switchbot_device.address: (switchbot_device, switchbot_device_adv)}

    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeStaticScanner("esp32", "esp32", connector)
    cancel = manager.async_register_scanner(scanner)

    assert scanner.discovered_devices_and_advertisement_data == {
        switchbot_device.address: (switchbot_device, switchbot_device_adv)
    }

    assert (
        async_scanner_devices_by_address(
            hass, switchbot_device.address, connectable=True
        )
        == []
    )
    devices = async_scanner_devices_by_address(
        hass, switchbot_device.address, connectable=False
    )
    assert len(devices) == 1
    assert devices[0].scanner == scanner
    assert devices[0].ble_device.name == switchbot_device.name
    assert devices[0].advertisement.local_name == switchbot_device_adv.local_name
    cancel()
