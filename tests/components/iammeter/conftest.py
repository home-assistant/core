"""Fixtures for IAMMETER tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from iammeter.client import Client
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.iammeter.const import DOMAIN

from . import MOCK_DATA, MOCK_INPUT


@pytest.fixture
def mock_meter() -> Generator[MagicMock]:
    """Mock the synchronous meter client."""
    with patch(
        "homeassistant.components.iammeter.coordinator.IamMeter", autospec=True
    ) as meter:
        meter.return_value.client = MagicMock(spec=Client)
        meter.return_value.measurement = MOCK_DATA.copy()
        meter.return_value.client.get_data.return_value = MOCK_DATA.copy()
        yield meter


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return a configured meter."""
    return MockConfigEntry(
        domain=DOMAIN, title="IamMeter", unique_id="test-meter", data=MOCK_INPUT
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip device setup in config flow tests."""
    with patch(
        "homeassistant.components.iammeter.async_setup_entry", return_value=None
    ) as setup:
        yield setup
