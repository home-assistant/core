"""Fixtures for Frank Energie integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from python_frank_energie.models import Authentication


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.frank_energie.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_frank_energie_api() -> MagicMock:
    """Return a mock bridge."""
    with patch(
        "homeassistant.components.frank_energie.config_flow.FrankEnergie",
    ) as mock:
        client = mock.return_value
        client.login.return_value = Authentication("auth_token", "refresh_token")

        yield mock
