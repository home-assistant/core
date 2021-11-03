"""Tests for the Zeroconf component."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def zc_mock_get_source_ip(mock_get_source_ip):
    """Enable the mock_get_source_ip fixture for all zeroconf tests."""
    return mock_get_source_ip


@pytest.fixture
def mock_async_zeroconf(mock_zeroconf):
    """Mock AsyncZeroconf."""
    with patch("homeassistant.components.zeroconf.HaAsyncZeroconf") as mock_aiozc:
        zc = mock_aiozc.return_value
        zc.async_register_service = AsyncMock()
        zc.zeroconf.async_wait_for_start = AsyncMock()
        zc.ha_async_close = AsyncMock()
        yield zc
