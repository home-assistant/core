"""Session fixtures."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakCharacteristicNotFoundError
from eurotronic_cometblue_ha import CometBlueBleakClient
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.eurotronic_cometblue.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from .const import (
    FIXTURE_DEVICE_NAME,
    FIXTURE_GATT_CHARACTERISTICS,
    FIXTURE_MAC,
    FIXTURE_RSSI,
    FIXTURE_SERVICE_UUID,
    FIXTURE_USER_INPUT,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device

# CometBlue device specific mocks and fixtures

FAKE_BLE_DEVICE = generate_ble_device(
    address=FIXTURE_MAC, name=FIXTURE_DEVICE_NAME, details={"path": "/dev/test"}
)

FAKE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=FIXTURE_DEVICE_NAME,
    address=FIXTURE_MAC,
    rssi=FIXTURE_RSSI,
    manufacturer_data={},
    service_data={},
    service_uuids=[FIXTURE_SERVICE_UUID],
    source="local",
    connectable=True,
    time=0,
    device=FAKE_BLE_DEVICE,
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


@pytest.fixture
def mock_service_info() -> Generator[None]:
    """Patch async_discovered_service_info a mocked device info."""
    with patch(
        "homeassistant.components.eurotronic_cometblue.config_flow.async_discovered_service_info",
        return_value=[FAKE_SERVICE_INFO],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_ble_device() -> Generator[None]:
    """Mock BLE device."""
    with (
        patch(
            "homeassistant.components.eurotronic_cometblue.async_ble_device_from_address",
            return_value=FAKE_BLE_DEVICE,
        ),
        patch(
            "homeassistant.components.eurotronic_cometblue.config_flow.async_ble_device_from_address",
            return_value=FAKE_BLE_DEVICE,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> Generator[None]:
    """Auto mock bluetooth."""

    with patch(
        "eurotronic_cometblue_ha.CometBlueBleakClient", MockCometBlueBleakClient
    ):
        yield


# Home Assistant related fixtures
@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create config entry mock from data."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: FIXTURE_MAC,
            **FIXTURE_USER_INPUT,
        },
        unique_id=format_mac(FIXTURE_MAC),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Patch async setup entry to return True."""
    with patch(
        "homeassistant.components.eurotronic_cometblue.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
