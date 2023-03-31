"""Test helpers."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.coronavirus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_cases():
    """Mock coronavirus cases."""
    with patch(
        "coronavirus.get_cases",
        return_value=[
            Mock(country="Netherlands", confirmed=10, recovered=8, deaths=1, current=1),
            Mock(country="Germany", confirmed=1, recovered=0, deaths=0, current=0),
            Mock(
                country="Sweden",
                confirmed=None,
                recovered=None,
                deaths=None,
                current=None,
            ),
        ],
    ) as mock_get_cases:
        yield mock_get_cases
