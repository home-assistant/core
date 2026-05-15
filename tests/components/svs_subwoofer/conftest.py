"""Fixtures for SVS Subwoofer tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto-enable the bluetooth integration in every test."""


@pytest.fixture
def mock_bleak_client() -> Generator[MagicMock]:
    """Patch bleak_retry_connector.establish_connection with a fake BleakClient."""
    client = MagicMock()
    client.is_connected = True
    client.connect = AsyncMock(return_value=None)
    client.disconnect = AsyncMock(return_value=None)
    client.start_notify = AsyncMock(return_value=None)
    client.write_gatt_char = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.svs_subwoofer.coordinator.establish_connection",
        new=AsyncMock(return_value=client),
    ):
        yield client
