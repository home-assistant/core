"""Common fixtures for the Cielo Home tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for the Cielo Home integration."""
    with patch(
        "homeassistant.components.cielo_home.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_cielo_client() -> Generator[AsyncMock]:
    """Mock the CieloClient to prevent actual API calls during init."""
    with patch(
        "homeassistant.components.cielo_home.coordinator.CieloClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value

        # Fake device
        dev = MagicMock()
        dev.id = "device_1"
        dev.name = "Living Room"
        dev.mac_address = "AA:BB:CC:DD:EE:FF"
        dev.device_status = True
        dev.preset_modes = ["sleep"]
        dev.humidity = 40

        mock_data = MagicMock()
        mock_data.raw = {}
        mock_data.parsed = {"device_1": dev}

        client.get_devices_data = AsyncMock(return_value=mock_data)

        yield client
