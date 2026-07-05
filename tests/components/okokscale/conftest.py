"""Common fixtures for the OKOK Scale tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.okokscale.const import DOMAIN

from . import OKOK_F0_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto-enable Bluetooth for all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent running the real integration setup during tests."""
    with patch(
        "homeassistant.components.okokscale.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, unique_id=OKOK_F0_ADDRESS)
