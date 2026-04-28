"""Fixtures for Specialized Turbo integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.specialized_turbo.const import DOMAIN
from homeassistant.const import CONF_ADDRESS

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

MOCK_ADDRESS = "DC:DD:BB:4A:D6:55"
MOCK_ADDRESS_FORMATTED = "dc:dd:bb:4a:d6:55"
MOCK_NAME = "SPECIALIZED"
MOCK_MANUFACTURER_DATA: dict[int, bytes] = {0x0059: b"TURBOHMItest1234"}

MOCK_TCU1_ADDRESS = "C6:1A:10:12:5E:48"
MOCK_TCU1_ADDRESS_FORMATTED = "c6:1a:10:12:5e:48"
MOCK_TCU1_NAME = "SPECIALIZED"
MOCK_TCU1_MANUFACTURER_DATA: dict[int, bytes] = {
    0x020D: bytes.fromhex("028657" + "ff" * 24),
}

TCX_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=MOCK_NAME,
    address=MOCK_ADDRESS,
    device=generate_ble_device(address=MOCK_ADDRESS, name=MOCK_NAME),
    rssi=-61,
    manufacturer_data=MOCK_MANUFACTURER_DATA,
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data=MOCK_MANUFACTURER_DATA,
        service_uuids=[],
    ),
    connectable=True,
    time=0,
    tx_power=None,
)

TCU1_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=MOCK_TCU1_NAME,
    address=MOCK_TCU1_ADDRESS,
    device=generate_ble_device(address=MOCK_TCU1_ADDRESS, name=MOCK_TCU1_NAME),
    rssi=-61,
    manufacturer_data=MOCK_TCU1_MANUFACTURER_DATA,
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data=MOCK_TCU1_MANUFACTURER_DATA,
        service_uuids=[],
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
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent actual entry setup during config flow tests."""
    with (
        patch(
            "homeassistant.components.specialized_turbo.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.specialized_turbo.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock_setup


@pytest.fixture
def mock_ble_connection() -> Generator[AsyncMock]:
    """Mock BLE connection for config flow tests."""
    mock_client = MagicMock()
    mock_client.disconnect = AsyncMock()
    with (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ) as mock_establish,
    ):
        yield mock_establish
