"""Fixtures for Emby integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.emby.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.100"
TEST_PORT = 8096
TEST_API_KEY = "test_api_key_123"
TEST_SERVER_ID = "abc123-server-id"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_HOST,
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_API_KEY: TEST_API_KEY,
            CONF_SSL: False,
        },
        unique_id=TEST_SERVER_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.emby.async_setup_entry", return_value=True
    ) as setup_mock:
        yield setup_mock


@pytest.fixture
def mock_emby_server() -> Generator[MagicMock]:
    """Mock the EmbyServer."""
    with patch("homeassistant.components.emby.EmbyServer", autospec=True) as mock_cls:
        mock_server = MagicMock()
        mock_server.devices = {}
        mock_server.stop = AsyncMock()
        mock_cls.return_value = mock_server
        yield mock_server
