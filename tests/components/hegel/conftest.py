"""Test fixtures for Hegel."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.hegel.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_connection_success() -> Generator[MagicMock]:
    """Mock successful HegelClient connection."""
    with patch(
        "homeassistant.components.hegel.config_flow.HegelClient",
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.ensure_connected = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client_class


@pytest.fixture
def mock_connection_error() -> Generator[MagicMock]:
    """Mock failed HegelClient connection."""
    with patch(
        "homeassistant.components.hegel.config_flow.HegelClient",
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.ensure_connected = AsyncMock(
            side_effect=OSError("Connection refused")
        )
        mock_client.stop = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client_class
