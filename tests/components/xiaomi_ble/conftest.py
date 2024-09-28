"""Session fixtures."""

from collections.abc import Generator
from unittest import mock

import pytest


class MockServices:
    """Mock GATTServicesCollection."""

    def get_characteristic(self, key: str) -> str:
        """Mock GATTServicesCollection.get_characteristic."""
        return key


class MockBleakClient:
    """Mock BleakClient."""

    services = MockServices()

    def __init__(self, *args, **kwargs) -> None:
        """Mock BleakClient."""

    async def __aenter__(self, *args, **kwargs):
        """Mock BleakClient.__aenter__."""
        return self

    async def __aexit__(self, *args, **kwargs):
        """Mock BleakClient.__aexit__."""

    async def connect(self, *args, **kwargs):
        """Mock BleakClient.connect."""

    async def disconnect(self, *args, **kwargs):
        """Mock BleakClient.disconnect."""


class MockBleakClientBattery5(MockBleakClient):
    """Mock BleakClient that returns a battery level of 5."""

    async def read_gatt_char(self, *args, **kwargs) -> bytes:
        """Mock BleakClient.read_gatt_char."""
        return b"\x05\x001.2.3"


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> Generator[None]:
    """Auto mock bluetooth."""

    with mock.patch("xiaomi_ble.parser.BleakClient", MockBleakClientBattery5):
        yield
