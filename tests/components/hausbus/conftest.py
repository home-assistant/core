"""Fixtures for the Haus-Bus integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_home_server() -> Generator[MagicMock]:
    """Mock the pyhausbus HomeServer used by the config flow and gateway.

    HomeServer opens a real UDP broadcast socket and starts background
    threads, so it must never be instantiated for real in tests. Both the
    config flow and the gateway obtain it through
    gateway.async_get_home_server, so patching it there covers both.
    """
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer"
    ) as mock_home_server_cls:
        mock_home_server = mock_home_server_cls.return_value
        mock_home_server.is_any_device_found.return_value = False
        yield mock_home_server
