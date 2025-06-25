"""Tests for the Bluetooth integration."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import bleak
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError
from habluetooth.usage import (
    install_multiple_bleak_catcher,
    uninstall_multiple_bleak_catcher,
)
import pytest

from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BaseHaRemoteScanner,
    HaBluetoothConnector,
    HomeAssistantBluetoothManager,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant

from . import _get_manager, generate_advertisement_data, generate_ble_device


@contextmanager
def mock_shutdown(manager: HomeAssistantBluetoothManager) -> Iterator[None]:
    """Mock shutdown of the HomeAssistantBluetoothManager."""
    manager.shutdown = True
    yield
    manager.shutdown = False


class FakeScanner(BaseHaRemoteScanner):
    """Fake scanner."""

    def __init__(
        self,
        scanner_id: str,
        name: str,
        connector: None,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(scanner_id, name, connector, connectable)
        self._details: dict[str, str | HaBluetoothConnector] = {}

    def __repr__(self) -> str:
        """Return the representation."""
        return f"FakeScanner({self.name})"

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
            device.details | {"scanner_specific_data": "test"},
            MONOTONIC_TIME(),
        )


class BaseFakeBleakClient:
    """Base class for fake bleak clients."""

    def __init__(self, address_or_ble_device: BLEDevice | str, **kwargs) -> None:
        """Initialize the fake bleak client."""
        self._device_path = "/dev/test"
        self._device = address_or_ble_device
        self._address = address_or_ble_device.address

    async def disconnect(self, *args, **kwargs):
        """Disconnect."""

    async def get_services(self, *args, **kwargs):
        """Get services."""
        return []


class FakeBleakClient(BaseFakeBleakClient):
    """Fake bleak client."""

    async def connect(self, *args, **kwargs):
        """Connect."""
        return True


class FakeBleakClientFailsToConnect(BaseFakeBleakClient):
    """Fake bleak client that fails to connect."""

    async def connect(self, *args, **kwargs):
        """Connect."""
        return False


class FakeBleakClientRaisesOnConnect(BaseFakeBleakClient):
    """Fake bleak client that raises on connect."""

    async def connect(self, *args, **kwargs):
        """Connect."""
        raise ConnectionError("Test exception")


def _generate_ble_device_and_adv_data(
    interface: str, mac: str, rssi: int
) -> tuple[BLEDevice, AdvertisementData]:
    """Generate a BLE device with adv data."""
    return (
        generate_ble_device(
            mac,
            "any",
            delegate="",
            details={"path": f"/org/bluez/{interface}/dev_{mac}"},
        ),
        generate_advertisement_data(rssi=rssi),
    )


@pytest.fixture(name="install_bleak_catcher")
def install_bleak_catcher_fixture():
    """Fixture that installs the bleak catcher."""
    install_multiple_bleak_catcher()
    yield
    uninstall_multiple_bleak_catcher()


@pytest.fixture(name="mock_platform_client")
def mock_platform_client_fixture():
    """Fixture that mocks the platform client."""
    with patch(
        "habluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClient,
    ):
        yield


@pytest.fixture(name="mock_platform_client_that_fails_to_connect")
def mock_platform_client_that_fails_to_connect_fixture():
    """Fixture that mocks the platform client that fails to connect."""
    with patch(
        "habluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientFailsToConnect,
    ):
        yield


@pytest.fixture(name="mock_platform_client_that_raises_on_connect")
def mock_platform_client_that_raises_on_connect_fixture():
    """Fixture that mocks the platform client that fails to connect."""
    with patch(
        "habluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientRaisesOnConnect,
    ):
        yield


def _generate_scanners_with_fake_devices(
    hass: HomeAssistant,
) -> tuple[
    dict[str, tuple[BLEDevice, AdvertisementData]], CALLBACK_TYPE, CALLBACK_TYPE
]:
    """Generate scanners with fake devices."""
    manager = _get_manager()
    hci0_device_advs = {}
    for i in range(10):
        device, adv_data = _generate_ble_device_and_adv_data(
            "hci0", f"00:00:00:00:00:{i:02x}", rssi=-60
        )
        hci0_device_advs[device.address] = (device, adv_data)
    hci1_device_advs = {}
    for i in range(10):
        device, adv_data = _generate_ble_device_and_adv_data(
            "hci1", f"00:00:00:00:00:{i:02x}", rssi=-80
        )
        hci1_device_advs[device.address] = (device, adv_data)

    scanner_hci0 = FakeScanner("00:00:00:00:00:01", "hci0", None, True)
    scanner_hci1 = FakeScanner("00:00:00:00:00:02", "hci1", None, True)

    for device, adv_data in hci0_device_advs.values():
        scanner_hci0.inject_advertisement(device, adv_data)

    for device, adv_data in hci1_device_advs.values():
        scanner_hci1.inject_advertisement(device, adv_data)

    cancel_hci0 = manager.async_register_scanner(scanner_hci0, connection_slots=2)
    cancel_hci1 = manager.async_register_scanner(scanner_hci1, connection_slots=1)

    return hci0_device_advs, cancel_hci0, cancel_hci1


@pytest.mark.usefixtures("enable_bluetooth", "two_adapters")
async def test_test_switch_adapters_when_out_of_slots(
    hass: HomeAssistant,
    install_bleak_catcher,
    mock_platform_client,
) -> None:
    """Ensure we try another scanner when one runs out of slots."""
    manager = _get_manager()
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    # hci0 has 2 slots, hci1 has 1 slot
    with (
        patch.object(manager.slot_manager, "release_slot") as release_slot_mock,
        patch.object(
            manager.slot_manager, "allocate_slot", return_value=True
        ) as allocate_slot_mock,
    ):
        ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
        client = bleak.BleakClient(ble_device)
        assert await client.connect() is True
        assert allocate_slot_mock.call_count == 1
        assert release_slot_mock.call_count == 0

    # All adapters are out of slots
    with (
        patch.object(manager.slot_manager, "release_slot") as release_slot_mock,
        patch.object(
            manager.slot_manager, "allocate_slot", return_value=False
        ) as allocate_slot_mock,
    ):
        ble_device = hci0_device_advs["00:00:00:00:00:02"][0]
        client = bleak.BleakClient(ble_device)
        with pytest.raises(bleak.exc.BleakError):
            await client.connect()
        assert allocate_slot_mock.call_count == 2
        assert release_slot_mock.call_count == 0

    # When hci0 runs out of slots, we should try hci1
    def _allocate_slot_mock(ble_device: BLEDevice):
        if "hci1" in ble_device.details["path"]:
            return True
        return False

    with (
        patch.object(manager.slot_manager, "release_slot") as release_slot_mock,
        patch.object(
            manager.slot_manager, "allocate_slot", _allocate_slot_mock
        ) as allocate_slot_mock,
    ):
        ble_device = hci0_device_advs["00:00:00:00:00:03"][0]
        client = bleak.BleakClient(ble_device)
        assert await client.connect() is True
        assert release_slot_mock.call_count == 0

    cancel_hci0()
    cancel_hci1()


@pytest.mark.usefixtures("enable_bluetooth", "two_adapters")
async def test_release_slot_on_connect_failure(
    hass: HomeAssistant,
    install_bleak_catcher,
    mock_platform_client_that_fails_to_connect,
) -> None:
    """Ensure the slot gets released on connection failure."""
    manager = _get_manager()
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    # hci0 has 2 slots, hci1 has 1 slot
    with (
        patch.object(manager.slot_manager, "release_slot") as release_slot_mock,
        patch.object(
            manager.slot_manager, "allocate_slot", return_value=True
        ) as allocate_slot_mock,
    ):
        ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
        client = bleak.BleakClient(ble_device)
        assert await client.connect() is False
        assert allocate_slot_mock.call_count == 1
        assert release_slot_mock.call_count == 1

    cancel_hci0()
    cancel_hci1()


@pytest.mark.usefixtures("enable_bluetooth", "two_adapters")
async def test_release_slot_on_connect_exception(
    hass: HomeAssistant,
    install_bleak_catcher,
    mock_platform_client_that_raises_on_connect,
) -> None:
    """Ensure the slot gets released on connection exception."""
    manager = _get_manager()
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    # hci0 has 2 slots, hci1 has 1 slot
    with (
        patch.object(manager.slot_manager, "release_slot") as release_slot_mock,
        patch.object(
            manager.slot_manager, "allocate_slot", return_value=True
        ) as allocate_slot_mock,
    ):
        ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
        client = bleak.BleakClient(ble_device)
        with pytest.raises(ConnectionError) as exc_info:
            await client.connect()
        assert str(exc_info.value) == "Test exception"
        assert allocate_slot_mock.call_count == 1
        assert release_slot_mock.call_count == 1

    cancel_hci0()
    cancel_hci1()


@pytest.mark.usefixtures("enable_bluetooth", "two_adapters")
async def test_passing_subclassed_str_as_address(
    hass: HomeAssistant,
    install_bleak_catcher,
) -> None:
    """Ensure the client wrapper can handle a subclassed str as the address."""
    _, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(hass)

    class SubclassedStr(str):
        __slots__ = ()

    address = SubclassedStr("00:00:00:00:00:01")
    client = bleak.BleakClient(address)

    class FakeBleakClient(BaseFakeBleakClient):
        """Fake bleak client."""

        async def connect(self, *args, **kwargs):
            """Connect."""
            return True

    with patch(
        "habluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClient,
    ):
        assert await client.connect() is True

    cancel_hci0()
    cancel_hci1()


@pytest.mark.usefixtures("enable_bluetooth", "two_adapters")
async def test_raise_after_shutdown(
    hass: HomeAssistant,
    install_bleak_catcher,
    mock_platform_client_that_raises_on_connect,
) -> None:
    """Ensure the slot gets released on connection exception."""
    manager = _get_manager()
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    # hci0 has 2 slots, hci1 has 1 slot
    with mock_shutdown(manager):
        ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
        client = bleak.BleakClient(ble_device)
        with pytest.raises(BleakError, match="shutdown"):
            await client.connect()
    cancel_hci0()
    cancel_hci1()
