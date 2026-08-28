"""Fixtures for the Haus-Bus integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.hausbus.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})


@pytest.fixture
def mock_home_server() -> Generator[MagicMock]:
    """Mock the pyhausbus HomeServer singleton used by the gateway."""
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer", autospec=True
    ) as mock_home_server_class:
        home_server = mock_home_server_class.return_value
        home_server.is_any_device_found.return_value = True
        yield home_server


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Bypass actually setting up the config entry."""
    with patch(
        "homeassistant.components.hausbus.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
