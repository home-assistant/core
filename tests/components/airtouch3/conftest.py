"""Common fixtures for the AirTouch 3 Air Conditioner tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airtouch3.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_background_discovery() -> Generator[AsyncMock]:
    """Prevent background discovery from opening sockets in tests."""
    with patch(
        "homeassistant.components.airtouch3.async_discover_devices",
        AsyncMock(return_value=[]),
    ) as mock_discovery:
        yield mock_discovery
