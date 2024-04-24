"""bosch_shc session fixtures."""

import pytest


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
