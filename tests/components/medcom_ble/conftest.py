"""Common fixtures for the Medcom Inspector BLE tests."""

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""
