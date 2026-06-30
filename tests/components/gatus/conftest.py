"""Common fixtures for the Gatus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gatus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_gatus_client() -> Generator[AsyncMock]:
    """Mock the third-party Gatus API client wrapper."""
    with patch(
        "homeassistant.components.gatus.coordinator.GatusClient", autospec=True
    ) as mock_client:
        client_instance = mock_client.return_value
        client_instance.get_endpoints_statuses = AsyncMock(return_value=[])
        yield client_instance
