"""Common fixtures for the AfterShip tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.aftership.const import DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aftership.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_aftership() -> Generator[AsyncMock]:
    """Mock the AfterShip client."""
    with patch(
        "homeassistant.components.aftership.AfterShip", return_value=AsyncMock()
    ) as mock_client:
        client = mock_client.return_value
        client.trackings.list.return_value = {"trackings": []}
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="AfterShip",
        data={CONF_API_KEY: "mock-api-key"},
    )
