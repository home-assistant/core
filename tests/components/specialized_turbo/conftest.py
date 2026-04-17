"""Fixtures for Specialized Turbo integration tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

MOCK_ADDRESS = "DC:DD:BB:4A:D6:55"
MOCK_ADDRESS_FORMATTED = "dc:dd:bb:4a:d6:55"
MOCK_NAME = "SPECIALIZED"
MOCK_MANUFACTURER_DATA: dict[int, bytes] = {0x0059: b"TURBOHMItest1234"}

# TCU1 (2018 Levo) test data
MOCK_TCU1_ADDRESS = "C6:1A:10:12:5E:48"
MOCK_TCU1_ADDRESS_FORMATTED = "c6:1a:10:12:5e:48"
MOCK_TCU1_NAME = "SPECIALIZED"
MOCK_TCU1_MANUFACTURER_DATA: dict[int, bytes] = {
    0x020D: bytes.fromhex("028657" + "ff" * 24),
}


@pytest.fixture(autouse=True)
def mock_bluetooth(
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
    """Mock out bluetooth from starting."""


def make_service_info(
    name: str = MOCK_NAME,
    address: str = MOCK_ADDRESS,
    manufacturer_data: dict[int, bytes] | None = None,
) -> MagicMock:
    """Create a mock BluetoothServiceInfoBleak."""
    info = MagicMock()
    info.name = name
    info.address = address
    info.manufacturer_data = (
        manufacturer_data if manufacturer_data is not None else MOCK_MANUFACTURER_DATA
    )
    return info


def make_tcu1_service_info(
    name: str = MOCK_TCU1_NAME,
    address: str = MOCK_TCU1_ADDRESS,
    manufacturer_data: dict[int, bytes] | None = None,
) -> MagicMock:
    """Create a mock BluetoothServiceInfoBleak for a TCU1 bike."""
    info = MagicMock()
    info.name = name
    info.address = address
    info.manufacturer_data = (
        manufacturer_data
        if manufacturer_data is not None
        else MOCK_TCU1_MANUFACTURER_DATA
    )
    return info
