"""Common fixtures for the OKOK Scale tests."""

from collections.abc import Generator
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.okokscale.const import DOMAIN

from . import OKOK_F0_SERVICE_INFO

from tests.common import MockConfigEntry

service_info = None


class MockServices:
    """Mock GATTServicesCollection."""

    def get_characteristic(self, key: str) -> str:
        """Mock GATTServicesCollection.get_characteristic."""
        return key


class MockBleakClient:
    """Mock BleakClient."""

    services = MockServices()

    is_connected = True

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

    async def read_gatt_char(self, id, *args, **kwargs) -> bytes:
        """Mock BleakClient.read_gatt_char."""
        return service_info.service_data[id]


@pytest.fixture
def mock_bluetooth(enable_bluetooth: None) -> Generator[None]:
    """Auto mock bluetooth."""

    with mock.patch("okokscale.parser.BleakClientWithServiceCache", MockBleakClient):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent running the real integration setup during tests."""
    with patch(
        "homeassistant.components.okokscale.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=OKOK_F0_SERVICE_INFO.address,
        data={},
        version=1,
        minor_version=2,
    )
