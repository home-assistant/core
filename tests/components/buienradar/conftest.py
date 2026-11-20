"""Test fixtures for buienradar."""

from collections.abc import Generator
import copy
from unittest.mock import AsyncMock, patch

import pytest

from . import TEST_DATA


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_buienradar_data() -> Generator[AsyncMock]:
    """Return parsed Buienradar data instead of fetching it."""
    with patch(
        "homeassistant.components.buienradar.coordinator.async_fetch_data",
        side_effect=lambda *args: copy.deepcopy(TEST_DATA),
    ) as mock_fetch:
        yield mock_fetch
