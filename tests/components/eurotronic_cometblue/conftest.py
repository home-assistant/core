"""Session fixtures."""

from collections.abc import Generator
from typing import Any
from unittest import mock
import uuid

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakCharacteristicNotFoundError
from eurotronic_cometblue_ha import CometBlueBleakClient
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from .const import (
    FIXTURE_DEVICE_NAME,
    FIXTURE_GATT_CHARACTERISTICS,
    FIXTURE_MAC,
    FIXTURE_RSSI,
    FIXTURE_SERVICE_UUID,
)

from tests.components.bluetooth import generate_ble_device

# CometBlue device specific mocks and fixtures


class MockCometBlueBleakClient(CometBlueBleakClient):
    """Mock BleakClient."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Mock init."""
        super().__init__(*args, **kwargs)
        self._device_path = "/dev/test"

    @property
    def is_connected(self) -> bool:
        """Mock connected."""
        return True

    async def connect(self, *args, **kwargs):
        """Mock connect."""

    async def disconnect(self, *args, **kwargs):
        """Mock disconnect."""

    async def get_services(self, *args, **kwargs):
        """Mock get_services."""
        return []

    async def clear_cache(self, *args, **kwargs):
        """Mock clear_cache."""
        return True

    def set_disconnected_callback(self, callback, **kwargs):
        """Mock set_disconnected_callback."""

    async def read_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID,
        **kwargs: Any,
    ) -> bytearray:
        """Mock read_gatt_char."""
        if not isinstance(char_specifier, (BleakGATTCharacteristic, str, uuid.UUID)):
            raise BleakCharacteristicNotFoundError(char_specifier)
        if isinstance(char_specifier, BleakGATTCharacteristic):
            char_specifier = char_specifier.uuid
        if not isinstance(char_specifier, uuid.UUID):
            char_specifier = uuid.UUID(char_specifier)
        try:
            return FIXTURE_GATT_CHARACTERISTICS[char_specifier]
        except KeyError:
            raise BleakCharacteristicNotFoundError(char_specifier)


# Bluetooth-related fixtures
def fake_service_info():
    """Return a BluetoothServiceInfoBleak for use in testing."""
    return BluetoothServiceInfoBleak(
        name=FIXTURE_DEVICE_NAME,
        address=FIXTURE_MAC,
        rssi=FIXTURE_RSSI,
        manufacturer_data={},
        service_data={},
        service_uuids=[FIXTURE_SERVICE_UUID],
        source="local",
        connectable=True,
        time=0,
        device=generate_ble_device(address=FIXTURE_MAC, name=FIXTURE_DEVICE_NAME),
        advertisement=AdvertisementData(
            local_name=FIXTURE_DEVICE_NAME,
            manufacturer_data={},
            service_data={},
            service_uuids=[FIXTURE_SERVICE_UUID],
            rssi=FIXTURE_RSSI,
            tx_power=-127,
            platform_data=(),
        ),
        tx_power=-127,
    )


@pytest.fixture
def mock_service_info() -> Generator[None]:
    """Patch async_discovered_service_info a mocked device info."""
    with mock.patch(
        "homeassistant.components.eurotronic_cometblue.config_flow.async_discovered_service_info",
        return_value=[fake_service_info()],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> Generator[None]:
    """Auto mock bluetooth."""

    with mock.patch(
        "eurotronic_cometblue_ha.CometBlueBleakClient", MockCometBlueBleakClient
    ):
        yield


# Home Assistant related fixtures
@pytest.fixture
def mock_setup_entry() -> Generator[mock.AsyncMock]:
    """Patch async setup entry to return True."""
    with mock.patch(
        "homeassistant.components.eurotronic_cometblue.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
