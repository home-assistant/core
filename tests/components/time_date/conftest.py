"""Fixtures for Time & Date integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.time_date.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
