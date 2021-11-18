"""devolo_home_control session fixtures."""

import pytest


@pytest.fixture(autouse=True)
def devolo_home_control_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
