"""Common fixtures for the Transport NSW tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_transport_nsw_api() -> Generator[AsyncMock]:
    """Mock the TransportNSW API."""
    with patch("TransportNSW.TransportNSW") as mock_api:
        mock_instance = AsyncMock()
        mock_api.return_value = mock_instance
        yield mock_instance
