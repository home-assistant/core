"""Fixtures for the Haus-Bus integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_home_server() -> Generator[MagicMock]:
    """Mock the pyhausbus HomeServer to avoid a real UDP socket and threads."""
    with (
        patch(
            "homeassistant.components.hausbus.config_flow.HomeServer"
        ) as mock_home_server_cls,
        patch(
            "homeassistant.components.hausbus.gateway.HomeServer",
            mock_home_server_cls,
        ),
    ):
        mock_home_server = mock_home_server_cls.return_value
        mock_home_server.is_any_device_found.return_value = False
        yield mock_home_server
