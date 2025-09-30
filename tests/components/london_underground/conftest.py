"""Fixtures for the london_underground tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=False)
def mock_setup_entry():
    """Prevent setup of integration during tests."""
    with patch(
        "homeassistant.components.london_underground.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
