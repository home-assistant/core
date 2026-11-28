"""Fixtures for the TCP tests."""

from collections.abc import Awaitable, Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tcp.const import DOMAIN
from homeassistant.core import HomeAssistant

CONFIG = {
    "name": "test_name",
    "host": "test_host",
    "port": 12345,
    "timeout": 11,
    "payload": "test_payload",
    "unit_of_measurement": "test_unit",
    "value_template": "{{ '7.' + value }}",
    "buffer_size": 1025,
    "ssl": False,
    "verify_ssl": True,
}


@pytest.fixture(name="mock_create_connection")
def mock_create_connection_fixture() -> Generator[MagicMock]:
    """Mock the TCP connection."""
    with patch("homeassistant.components.tcp.entity.socket.create_connection") as mock:
        mock.return_value.__enter__.return_value.recv.return_value = b"123"
        yield mock


@pytest.fixture(name="mock_socket")
def mock_socket_fixture(mock_create_connection: MagicMock) -> MagicMock:
    """Return the connected socket."""
    return mock_create_connection.return_value.__enter__.return_value


@pytest.fixture(name="mock_ssl_context")
def mock_ssl_context_fixture() -> Generator[MagicMock]:
    """Mock the SSL context."""
    with patch(
        "homeassistant.components.tcp.entity.ssl.create_default_context"
    ) as mock:
        mock.return_value.wrap_socket.return_value.recv.return_value = b"123567"
        yield mock


@pytest.fixture(name="setup_tcp")
def setup_tcp_fixture(
    hass: HomeAssistant, mock_socket: MagicMock
) -> Callable[..., Awaitable[MockConfigEntry]]:
    """Return a function that sets up an entry."""

    async def _setup(**overrides: Any) -> MockConfigEntry:
        data = {**CONFIG, **overrides}
        entry = MockConfigEntry(domain=DOMAIN, title=data["name"], data=data)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup
