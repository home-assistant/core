"""Test the snapcast config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.snapcast.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_create_server() -> Generator[AsyncMock, None, None]:
    """Create mock snapcast connection."""
    mock_connection = AsyncMock()
    mock_connection.start = AsyncMock(return_value=None)
    mock_connection.stop = MagicMock()
    with patch("snapcast.control.create_server", return_value=mock_connection):
        yield mock_connection
