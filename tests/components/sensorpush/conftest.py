"""SensorPush session fixtures."""

import pytest


@pytest.fixture(autouse=True)
def auto_mock_bleak_scanner_start(mock_bleak_scanner_start):
    """Auto mock bleak scanner start."""
