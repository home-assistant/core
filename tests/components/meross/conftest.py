"""Meross Bluetooth session fixtures."""

import pytest


@pytest.fixture
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Mock bluetooth for setup and entity tests."""
