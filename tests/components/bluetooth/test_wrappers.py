"""Tests for the Bluetooth integration."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import patch

import bleak
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
import pytest

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothServiceInfoBleak,
    HaBluetoothConnector,
    async_get_advertisement_callback,
)
from homeassistant.components.bluetooth.usage import (
    install_multiple_bleak_catcher,
    uninstall_multiple_bleak_catcher,
)
from homeassistant.core import HomeAssistant

from . import _get_manager, generate_advertisement_data, generate_ble_device


class FakeScanner(BaseHaRemoteScanner):
    """Fake scanner."""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        name: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: None,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(
            hass, scanner_id, name, new_info_callback, connector, connectable
        )
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
        )


class BaseFakeBleakClient:
    """Base class for fake bleak clients."""

    def __init__(self, address_or_ble_device: BLEDevice | str, **kwargs):
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
        raise Exception("Test exception")


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
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClient,
    ):
        yield


@pytest.fixture(name="mock_platform_client_that_fails_to_connect")
def mock_platform_client_that_fails_to_connect_fixture():
    """Fixture that mocks the platform client that fails to connect."""
    with patch(
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientFailsToConnect,
    ):
        yield


@pytest.fixture(name="mock_platform_client_that_raises_on_connect")
def mock_platform_client_that_raises_on_connect_fixture():
    """Fixture that mocks the platform client that fails to connect."""
    with patch(
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientRaisesOnConnect,
    ):
        yield


def _generate_scanners_with_fake_devices(hass):
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

    new_info_callback = async_get_advertisement_callback(hass)
    scanner_hci0 = FakeScanner(
        hass, "00:00:00:00:00:01", "hci0", new_info_callback, None, True
    )
    scanner_hci1 = FakeScanner(
        hass, "00:00:00:00:00:02", "hci1", new_info_callback, None, True
    )

    for device, adv_data in hci0_device_advs.values():
        scanner_hci0.inject_advertisement(device, adv_data)

    for device, adv_data in hci1_device_advs.values():
        scanner_hci1.inject_advertisement(device, adv_data)

    cancel_hci0 = manager.async_register_scanner(scanner_hci0, True, 2)
    cancel_hci1 = manager.async_register_scanner(scanner_hci1, True, 1)

    return hci0_device_advs, cancel_hci0, cancel_hci1


async def test_test_switch_adapters_when_out_of_slots(
    hass: HomeAssistant,
    two_adapters: None,
    enable_bluetooth: None,
    install_bleak_catcher,
    mock_platform_client,
) -> None:
    """Ensure we try another scanner when one runs out of slots."""
    manager = _get_manager()
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    # hci0 has 2 slots, hci1 has 1 slot
    with patch.object(
        manager.slot_manager, "release_slot"
    ) as release_slot_mock, patch.object(
        manager.slot_manager, "allocate_slot", return_value=True
    ) as allocate_slot_mock:
        ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
        client = bleak.BleakClient(ble_device)
        assert await client.connect() is True
        assert allocate_slot_mock.call_count == 1
        assert release_slot_mock.call_count == 0

    # All adapters are out of slots
    with patch.object(
        manager.slot_manager, "release_slot"
    ) as release_slot_mock, patch.object(
        manager.slot_manager, "allocate_slot", return_value=False
    ) as allocate_slot_mock:
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

    with patch.object(
        manager.slot_manager, "release_slot"
    ) as release_slot_mock, patch.object(
        manager.slot_manager, "allocate_slot", _allocate_slot_mock
    ) as allocate_slot_mock:
        ble_device = hci0_device_advs["00:00:00:00:00:03"][0]
        client = bleak.BleakClient(ble_device)
        await client.connect() is True
        assert release_slot_mock.call_count == 0

    cancel_hci0()
    cancel_hci1()


async def test_release_slot_on_connect_failure(
    hass: HomeAssistant,
    two_adapters: None,
    enable_bluetooth: None,
    install_bleak_catcher,
    mock_platform_client_that_fails_to_connect,
) -> None:
    """Ensure the slot gets released on connection failure."""
    manager = _get_manager()
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    # hci0 has 2 slots, hci1 has 1 slot
    with patch.object(
        manager.slot_manager, "release_slot"
    ) as release_slot_mock, patch.object(
        manager.slot_manager, "allocate_slot", return_value=True
    ) as allocate_slot_mock:
        ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
        client = bleak.BleakClient(ble_device)
        assert await client.connect() is False
        assert allocate_slot_mock.call_count == 1
        assert release_slot_mock.call_count == 1

    cancel_hci0()
    cancel_hci1()


async def test_release_slot_on_connect_exception(
    hass: HomeAssistant,
    two_adapters: None,
    enable_bluetooth: None,
    install_bleak_catcher,
    mock_platform_client_that_raises_on_connect,
) -> None:
    """Ensure the slot gets released on connection exception."""
    manager = _get_manager()
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    # hci0 has 2 slots, hci1 has 1 slot
    with patch.object(
        manager.slot_manager, "release_slot"
    ) as release_slot_mock, patch.object(
        manager.slot_manager, "allocate_slot", return_value=True
    ) as allocate_slot_mock:
        ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
        client = bleak.BleakClient(ble_device)
        with pytest.raises(Exception):
            assert await client.connect() is False
        assert allocate_slot_mock.call_count == 1
        assert release_slot_mock.call_count == 1

    cancel_hci0()
    cancel_hci1()


async def test_we_switch_adapters_on_failure(
    hass: HomeAssistant,
    two_adapters: None,
    enable_bluetooth: None,
    install_bleak_catcher,
) -> None:
    """Ensure we try the next best adapter after a failure."""
    hci0_device_advs, cancel_hci0, cancel_hci1 = _generate_scanners_with_fake_devices(
        hass
    )
    ble_device = hci0_device_advs["00:00:00:00:00:01"][0]
    client = bleak.BleakClient(ble_device)

    class FakeBleakClientFailsHCI0Only(BaseFakeBleakClient):
        """Fake bleak client that fails to connect."""

        async def connect(self, *args, **kwargs):
            """Connect."""
            if "/hci0/" in self._device.details["path"]:
                return False
            return True

    with patch(
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientFailsHCI0Only,
    ):
        assert await client.connect() is False

    with patch(
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientFailsHCI0Only,
    ):
        assert await client.connect() is False

    # After two tries we should switch to hci1
    with patch(
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientFailsHCI0Only,
    ):
        assert await client.connect() is True

    # ..and we remember that hci1 works as long as the client doesn't change
    with patch(
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientFailsHCI0Only,
    ):
        assert await client.connect() is True

    # If we replace the client, we should try hci0 again
    client = bleak.BleakClient(ble_device)

    with patch(
        "homeassistant.components.bluetooth.wrappers.get_platform_client_backend_type",
        return_value=FakeBleakClientFailsHCI0Only,
    ):
        assert await client.connect() is False
    cancel_hci0()
    cancel_hci1()
