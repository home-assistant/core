"""triggercmd conftest."""

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_async_setup_entry():
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.triggercmd.async_setup_entry",
        return_value=True,
    ) as mock_async_setup_entry:
        yield mock_async_setup_entry
