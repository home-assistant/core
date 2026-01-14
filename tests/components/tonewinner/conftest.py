"""Common fixtures for the ToneWinner AT-500 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from serial_asyncio_fast import SerialTransport

from homeassistant.components.tonewinner.const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    DOMAIN,
)


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MagicMock(
        entry_id="test_entry_id",
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: 9600,
        },
        options={},
        title="Tonewinner AT-500",
        domain=DOMAIN,
    )


@pytest.fixture
def mock_serial_connection():
    """Mock serial connection."""
    transport = MagicMock(spec=SerialTransport)
    transport.write = MagicMock()
    transport.close = MagicMock()
    transport.protocol = MagicMock()

    with patch(
        "serial_asyncio_fast.create_serial_connection",
        return_value=(transport, MagicMock()),
    ):
        yield transport


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return ["media_player"]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.tonewinner.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
