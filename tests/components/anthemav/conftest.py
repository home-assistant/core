"""Fixtures for anthemav integration tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_anthemav() -> AsyncMock:
    """Return the default mocked anthemav."""
    avr = AsyncMock()
    avr.protocol.macaddress = "000000000001"
    avr.protocol.model = "MRX 520"
    avr.reconnect = AsyncMock()
    avr.close = MagicMock()
    avr.protocol.input_list = []
    avr.protocol.audio_listening_mode_list = []
    return avr


@pytest.fixture
def mock_connection_create(mock_anthemav: AsyncMock) -> AsyncMock:
    """Return the default mocked connection.create."""

    with patch(
        "anthemav.Connection.create",
        return_value=mock_anthemav,
    ) as mock:
        yield mock
