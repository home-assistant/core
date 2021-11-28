"""Fixtures for anthemav integration tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_anthemav() -> MagicMock:
    """Return the default mocked anthemav."""
    avr = MagicMock()
    avr.protocol.macaddress = "000000000001"
    avr.protocol.model = "MRX 520"
    avr.reconnect = AsyncMock()
    avr.protocol.input_list = []
    avr.protocol.audio_listening_mode_list = []
    return avr


@pytest.fixture
def mock_connection_create(mock_avr: MagicMock) -> AsyncMock:
    """Return the default mocked connection.create."""

    def connectioncreate(host, port, update_callback, auto_reconnect=True):
        update_callback("IDM")
        update_callback("IDN")
        return mock_avr

    with patch(
        "anthemav.Connection.create",
        side_effect=connectioncreate,
    ) as mock:
        yield mock
