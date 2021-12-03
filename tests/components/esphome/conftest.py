"""esphome session fixtures."""

import pytest


@pytest.fixture(autouse=True)
def esphome_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
