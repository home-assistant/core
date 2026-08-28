"""Test fixtures for Hegel."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hegel.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MODEL

from .const import TEST_HOST, TEST_MODEL, TEST_UDN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.hegel.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_hegel_client() -> Generator[MagicMock]:
    """Mock successful HegelClient connection."""
    with patch(
        "homeassistant.components.hegel.config_flow.HegelClient", autospec=True
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.start = AsyncMock()
        mock_client.ensure_connected = AsyncMock()
        mock_client.stop = AsyncMock()
        yield mock_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock failed HegelClient connection."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_MODEL: TEST_MODEL},
        unique_id=TEST_UDN,
    )
