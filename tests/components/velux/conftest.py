"""Configuration for Velux tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.zeroconf import HaAsyncZeroconf


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.velux.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_velux_discovery() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "pyvlx.discovery.VeluxDiscovery._async_discover_hosts",
        autospec=True,
    ) as mock_velux_discovery:
        yield mock_velux_discovery


@pytest.fixture
def mock_async_zeroconf(mock_zeroconf: None) -> Generator[None, None, None]:
    """Mock AsyncZeroconf."""
    with patch(
        "homeassistant.components.zeroconf.HaAsyncZeroconf", spec=HaAsyncZeroconf
    ) as mock_aiozc:
        yield mock_aiozc
