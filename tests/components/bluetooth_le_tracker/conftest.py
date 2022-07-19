"""Tests for the bluetooth_le_tracker component."""
import pytest


@pytest.fixture(autouse=True)
def bluetooth_le_tracker_auto_mock_bluetooth(mock_bluetooth):
    """Mock the bluetooth integration scanner."""
