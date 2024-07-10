"""Test fixtures for Russound RIO integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.russound_rio.const import DOMAIN

from .const import HARDWARE_MAC, MOCK_CONFIG, MODEL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Prevent setup."""
    with patch(
        "homeassistant.components.russound_rio.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=HARDWARE_MAC, title=MODEL
    )


@pytest.fixture
def mock_russound() -> Generator[AsyncMock]:
    """Mock the Russound RIO client."""
    with (
        patch(
            "homeassistant.components.russound_rio.Russound", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.russound_rio.config_flow.Russound",
            new=mock_client,
        ),
    ):
        mock_client.enumerate_controllers.return_value = [(1, HARDWARE_MAC, MODEL)]
        yield mock_client
