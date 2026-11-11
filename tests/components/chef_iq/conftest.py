"""Chef iQ test fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.chef_iq.const import DOMAIN

from . import ADDRESS


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto-enable Bluetooth for all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.chef_iq.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS)
