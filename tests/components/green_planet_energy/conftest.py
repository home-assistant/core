"""Test fixtures for Green Planet Energy integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Green Planet Energy",
        domain=DOMAIN,
        data={},
        unique_id="green_planet_energy",
    )


@pytest.fixture
def mock_api():
    """Mock the Green Planet Energy API."""
    mock_response_data = {
        "result": {
            "verbrauchspreise": [
                {"zeitpunkt": "2025-08-01T09:00:00", "preis": 0.25},
                {"zeitpunkt": "2025-08-01T10:00:00", "preis": 0.30},
                {"zeitpunkt": "2025-08-01T11:00:00", "preis": 0.28},
                {"zeitpunkt": "2025-08-01T12:00:00", "preis": 0.32},
                {"zeitpunkt": "2025-08-01T13:00:00", "preis": 0.29},
                {"zeitpunkt": "2025-08-01T14:00:00", "preis": 0.27},
                {"zeitpunkt": "2025-08-01T15:00:00", "preis": 0.31},
                {"zeitpunkt": "2025-08-01T16:00:00", "preis": 0.33},
                {"zeitpunkt": "2025-08-01T17:00:00", "preis": 0.35},
                {"zeitpunkt": "2025-08-01T18:00:00", "preis": 0.30},
            ]
        }
    }

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)

    mock_session = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = mock_response

    with patch(
        "homeassistant.components.green_planet_energy.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        yield mock_session


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
