"""Test fixtures for Russound RIO integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.russound_rio.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import HARDWARE_MAC, MOCK_CONFIG, MOCK_CONTROLLERS, MODEL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Prevent setup."""
    with patch(
        "homeassistant.components.russound_rio.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a Russound RIO config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=HARDWARE_MAC, title=MODEL
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_russound() -> Generator[AsyncMock]:
    """Mock the Russound RIO client."""
    with (
        patch(
            "homeassistant.components.russound_rio.RussoundClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.russound_rio.config_flow.RussoundClient",
            return_value=mock_client,
        ),
    ):
        mock_client.controllers = MOCK_CONTROLLERS
        yield mock_client
