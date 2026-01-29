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
    """Mock successful TCP connection."""
    with patch(
        "homeassistant.components.hegel.config_flow.asyncio.open_connection",
        return_value=(AsyncMock(), AsyncMock()),
    ) as mock_conn:
        yield mock_conn


@pytest.fixture
def mock_connection_error() -> Generator[MagicMock]:
    """Mock failed TCP connection."""
    with patch(
        "homeassistant.components.hegel.config_flow.asyncio.open_connection",
        side_effect=OSError("Connection refused"),
    ) as mock_conn:
        yield mock_conn
