"""default_config session fixtures."""

import pytest


@pytest.fixture(autouse=True)
def default_config_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
