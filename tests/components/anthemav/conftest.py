"""Fixtures for anthemav integration tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.anthemav.const import CONF_MODEL, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT

from tests.common import MockConfigEntry


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
    avr.protocol.power = False
    return avr


@pytest.fixture
def mock_connection_create(mock_anthemav: AsyncMock) -> AsyncMock:
    """Return the default mocked connection.create."""

    with patch(
        "anthemav.Connection.create",
        return_value=mock_anthemav,
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 14999,
            CONF_NAME: "Anthem AV",
            CONF_MAC: "00:00:00:00:00:01",
            CONF_MODEL: "MRX 520",
        },
        unique_id="00:00:00:00:00:01",
    )
