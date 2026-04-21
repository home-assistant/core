"""Test fixtures for Russound RNET integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.russound_rnet.const import DOMAIN

from .const import MOCK_SERIAL_CONFIG, MOCK_TCP_CONFIG, MODEL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent setup."""
    with patch(
        "homeassistant.components.russound_rnet.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a TCP config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_TCP_CONFIG,
        title=MODEL,
        unique_id="192.168.1.100:9999",
    )


@pytest.fixture
def mock_serial_config_entry() -> MockConfigEntry:
    """Mock a serial config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SERIAL_CONFIG,
        title=MODEL,
        unique_id="/dev/ttyUSB0",
    )


@pytest.fixture
def mock_russound_client() -> Generator[AsyncMock]:
    """Mock the Russound RNET client."""
    mock_zone_info = MagicMock()
    mock_zone_info.power = True
    mock_zone_info.volume = 25
    mock_zone_info.source = 1

    with (
        patch(
            "homeassistant.components.russound_rnet.RussoundRNETClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.russound_rnet.config_flow.RussoundRNETClient",
            new=mock_client_class,
        ),
        patch(
            "homeassistant.components.russound_rnet.repairs.RussoundRNETClient",
            new=mock_client_class,
        ),
        patch(
            "homeassistant.components.russound_rnet.RussoundTcpConnectionHandler",
        ),
        patch(
            "homeassistant.components.russound_rnet.config_flow.RussoundTcpConnectionHandler",
        ),
        patch(
            "homeassistant.components.russound_rnet.repairs.RussoundTcpConnectionHandler",
        ),
        patch(
            "homeassistant.components.russound_rnet.RussoundSerialConnectionHandler",
        ),
        patch(
            "homeassistant.components.russound_rnet.config_flow.RussoundSerialConnectionHandler",
        ),
    ):
        client = mock_client_class.return_value
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.is_connected = True
        client.get_all_zone_info = AsyncMock(return_value=mock_zone_info)
        client.set_zone_power = AsyncMock()
        client.set_volume = AsyncMock()
        client.select_source = AsyncMock()
        client.toggle_mute = AsyncMock()

        yield client
