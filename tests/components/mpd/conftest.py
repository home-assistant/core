"""Fixtures for Music Player Daemon integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.mpd.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Music Player Daemon",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.0.1", CONF_PORT: 6600, CONF_PASSWORD: "test123"},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mpd.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mpd_client() -> Generator[MagicMock]:
    """Return a mock for Music Player Daemon client."""

    with patch(
        "homeassistant.components.mpd.config_flow.MPDClient",
        autospec=True,
    ) as mpd_client:
        client = mpd_client.return_value
        client.password = AsyncMock()
        yield client
