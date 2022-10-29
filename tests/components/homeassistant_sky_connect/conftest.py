"""Test fixtures for the Home Assistant Sky Connect integration."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_zha():
    """Mock the zha integration."""
    with patch(
        "homeassistant.components.zha.async_setup_entry",
        return_value=True,
    ):
        yield
