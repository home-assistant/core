"""Common fixtures for the Gardena Bluetooth tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from bleak import BleakClient

# from tests.components.bluetooth import (
#    MockBleakClient,
# )
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.service import BleakGATTServiceCollection
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gardena_bluetooth.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_client(enable_bluetooth):
    """Auto mock bluetooth."""

    client = Mock(spec_set=BleakClient)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.services = Mock(spec_set=BleakGATTServiceCollection)
    client.services.get_characteristic = Mock()
    client.services.get_characteristic.return_value = Mock(spec=BleakGATTCharacteristic)
    client.services.get_characteristic.return_value.properties = ["read"]
    client.read_gatt_char = AsyncMock(return_value=b"")

    with patch(
        "homeassistant.components.gardena_bluetooth.config_flow.BleakClient",
        return_value=client,
    ):
        yield client
