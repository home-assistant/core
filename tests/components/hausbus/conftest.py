"""Fixtures for the Haus-Bus integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.hausbus import gateway as hausbus_gateway
from homeassistant.components.hausbus.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def _reset_home_server_broken_flag() -> Generator[None]:
    """Reset the module-level broken-HomeServer flag between tests.

    Unlike the reference-count WeakKeyDictionary it lives alongside, this
    flag is not tied to any object's lifetime, so it would otherwise stay
    set for every test running after one that intentionally triggers it.
    """
    yield
    hausbus_gateway._home_server_broken_state.broken = False


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Haus-Bus", data={})


@pytest.fixture
def mock_home_server_class() -> Generator[MagicMock]:
    """Mock the pyhausbus HomeServer class used by the gateway."""
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer", autospec=True
    ) as mock_home_server_class:
        yield mock_home_server_class


@pytest.fixture
def mock_home_server(mock_home_server_class: MagicMock) -> MagicMock:
    """Mock the pyhausbus HomeServer singleton used by the gateway."""
    home_server = mock_home_server_class.return_value
    home_server.is_any_device_found.return_value = True
    return home_server


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Bypass actually setting up the config entry."""
    with patch(
        "homeassistant.components.hausbus.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
