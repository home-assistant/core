"""Music Assistant test fixtures."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf: MagicMock):
    """Mock zeroconf in all tests."""


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.mass.async_setup_entry", return_value=True):
        yield
