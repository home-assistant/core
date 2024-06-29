"""Fixtures for Pinecil tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from habluetooth import BluetoothServiceInfoBleak
import pytest

from homeassistant.const import CONF_ADDRESS

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

USER_INPUT = {CONF_ADDRESS: "c0:ff:ee:c0:ff:ee"}
DEFAULT_NAME = "Pinecil-C0FFEEE"
PINECIL_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Pinecil-C0FFEEE",
    address="c0:ff:ee:c0:ff:ee",
    device=generate_ble_device(
        address="c0:ff:ee:c0:ff:ee",
        name="Pinecil-C0FFEEE",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=["9eae1000-9d0d-48c5-aa55-33e27f9bc533"],
    ),
    connectable=True,
    time=0,
    tx_power=None,
)

UNKNOWN_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="",
    address="c0:ff:ee:c0:ff:ee",
    device=generate_ble_device(
        address="c0:ff:ee:c0:ff:ee",
        name="",
    ),
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={},
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
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pinecil.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="discovery")
def mock_async_discovered_service_info() -> Generator[MagicMock]:
    """Mock service discovery."""
    with patch(
        "homeassistant.components.pinecil.config_flow.async_discovered_service_info",
        return_value=[PINECIL_SERVICE_INFO, UNKNOWN_SERVICE_INFO],
    ) as discovery:
        yield discovery
