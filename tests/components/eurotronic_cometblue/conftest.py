"""Session fixtures."""

from collections.abc import Buffer, Generator
from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakCharacteristicNotFoundError
from eurotronic_cometblue_ha import CometBlueBleakClient
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.eurotronic_cometblue import PLATFORMS
from homeassistant.components.eurotronic_cometblue.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import (
    FIXTURE_DEFAULT_CHARACTERISTICS,
    FIXTURE_DEVICE_NAME,
    FIXTURE_MAC,
    FIXTURE_RSSI,
    FIXTURE_SERVICE_UUID,
    FIXTURE_USER_INPUT,
    WRITEABLE_CHARACTERISTICS,
    WRITEABLE_CHARACTERISTICS_ALLOW_UNCHANGED,
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


def _normalize_characteristic(
    char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID,
) -> uuid.UUID:
    """Normalize a characteristic specifier to UUID."""
    if not isinstance(char_specifier, (BleakGATTCharacteristic, str, uuid.UUID)):
        raise BleakCharacteristicNotFoundError(char_specifier)
    if isinstance(char_specifier, BleakGATTCharacteristic):
        char_specifier = char_specifier.uuid
    if not isinstance(char_specifier, uuid.UUID):
        char_specifier = uuid.UUID(char_specifier)
    return char_specifier


class MockCometBlueBleakClient(CometBlueBleakClient):
    """Mock BleakClient."""

    characteristics: dict[uuid.UUID, bytearray] = {}

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
        char_specifier = _normalize_characteristic(char_specifier)
        try:
            return bytearray(self.characteristics[char_specifier])
        except KeyError:
            raise BleakCharacteristicNotFoundError(char_specifier)

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID,
        data: Buffer,
        response: bool | None = None,
    ) -> None:
        """Mock write_gatt_char."""
        char_specifier = _normalize_characteristic(char_specifier)
        if char_specifier not in WRITEABLE_CHARACTERISTICS:
            raise BleakCharacteristicNotFoundError(char_specifier)
        data = bytearray(data)
        # when writing temperature it is possible that 128 will be sent, meaning "no change"
        # we have to restore the original value in this case to keep tests working
        if char_specifier in WRITEABLE_CHARACTERISTICS_ALLOW_UNCHANGED:
            for i, byte in enumerate(data):
                if byte == 128:
                    data[i] = self.characteristics[char_specifier][i]
        self.characteristics[char_specifier] = data


@pytest.fixture
def mock_gatt_characteristics() -> dict[uuid.UUID, bytearray]:
    """Provide a mutable per-test GATT characteristic store."""
    return {
        characteristic: bytearray(value)
        for characteristic, value in FIXTURE_DEFAULT_CHARACTERISTICS.items()
    }


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
def mock_bluetooth(
    enable_bluetooth: None,
    mock_gatt_characteristics: dict[uuid.UUID, bytearray],
) -> Generator[None]:
    """Auto mock bluetooth."""

    MockCometBlueBleakClient.characteristics = mock_gatt_characteristics
    with (
        patch(
            "homeassistant.components.eurotronic_cometblue.entity.bluetooth.async_address_present",
            return_value=True,
        ),
        patch(
            "homeassistant.components.eurotronic_cometblue.coordinator.COMMAND_RETRY_INTERVAL",
            0,
        ),
        patch("eurotronic_cometblue_ha.CometBlueBleakClient", MockCometBlueBleakClient),
    ):
        yield
    MockCometBlueBleakClient.characteristics = {}


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


async def setup_with_selected_platforms(
    hass: HomeAssistant, entry: MockConfigEntry, platforms: list[Platform] | None = None
) -> None:
    """Set up the Eurotronic Comet Blue integration with the selected platforms."""
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.eurotronic_cometblue.PLATFORMS",
        platforms or PLATFORMS,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
