"""Fixtures for Specialized Turbo integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError
from habluetooth import BluetoothServiceInfoBleak
import pytest

from homeassistant.components.specialized_turbo.const import DOMAIN
from homeassistant.const import CONF_ADDRESS

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

MOCK_ADDRESS = "DC:DD:BB:4A:D6:55"
MOCK_ADDRESS_FORMATTED = "dc:dd:bb:4a:d6:55"
MOCK_NAME = "SPECIALIZED"
MOCK_MANUFACTURER_DATA: dict[int, bytes] = {0x0059: b"TURBOHMItest1234"}

MOCK_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=MOCK_NAME,
    address=MOCK_ADDRESS,
    device=generate_ble_device(
        address=MOCK_ADDRESS,
        name=MOCK_NAME,
    ),
    rssi=-61,
    manufacturer_data=MOCK_MANUFACTURER_DATA,
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data=MOCK_MANUFACTURER_DATA,
    ),
    connectable=True,
    time=0,
    tx_power=None,
)

NOT_SPECIALIZED_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Other Device",
    address="AA:BB:CC:DD:EE:FF",
    device=generate_ble_device(
        address="AA:BB:CC:DD:EE:FF",
        name="Other Device",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
    ),
    connectable=True,
    time=0,
    tx_power=None,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS, "pin": 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent actual entry setup during config flow tests."""
    with patch(
        "homeassistant.components.specialized_turbo.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


def mock_connection_success() -> tuple[MagicMock, AsyncMock]:
    """Return context managers for a successful BLE connection test."""
    mock_client = MagicMock()
    mock_client.disconnect = AsyncMock()
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    )


def mock_connection_failure_no_device() -> tuple[MagicMock, AsyncMock]:
    """Return context managers for a failed BLE connection (device not found)."""
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
        ),
    )


def mock_connection_failure_bleak_error() -> tuple[MagicMock, AsyncMock]:
    """Return context managers for a failed BLE connection (BleakError)."""
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            side_effect=BleakError("Connection failed"),
        ),
    )


def mock_connection_failure_timeout() -> tuple[MagicMock, AsyncMock]:
    """Return context managers for a failed BLE connection (TimeoutError)."""
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            side_effect=TimeoutError,
        ),
    )
