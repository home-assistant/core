"""OralB session fixtures."""

from collections.abc import Generator
from typing import Any
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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


class MockBleakClientBattery49(MockBleakClient):
    """Mock BleakClient that returns a battery level of 49."""

    async def read_gatt_char(self, *args, **kwargs) -> bytes:
        """Mock BleakClient.read_gatt_char."""
        return b"\x31\x00"


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> Generator[None]:
    """Auto mock bluetooth."""

    with mock.patch(
        "oralb_ble.parser.BleakClientWithServiceCache", MockBleakClientBattery49
    ):
        yield
