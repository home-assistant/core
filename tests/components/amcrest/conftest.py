"""Common fixtures for the Amcrest tests."""
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Iterator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.amcrest.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
