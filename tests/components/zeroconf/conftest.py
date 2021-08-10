"""Tests for the Zeroconf component."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_async_zeroconf():
    """Mock AsyncZeroconf."""
    with patch("homeassistant.components.zeroconf.HaAsyncZeroconf") as mock_aiozc:
        zc = mock_aiozc.return_value
        zc.async_register_service = AsyncMock()
        zc.zeroconf.async_wait_for_start = AsyncMock()
        zc.ha_async_close = AsyncMock()
        yield zc
