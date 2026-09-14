"""default_config session fixtures."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def default_config_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""
