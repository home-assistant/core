"""Configuration for ISS tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.iss.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_pyiss() -> Generator[MagicMock]:
    """Mock the pyiss.ISS class."""
    with patch("homeassistant.components.iss.coordinator.pyiss.ISS") as mock_iss_class:
        mock_iss = MagicMock()
        mock_iss.number_of_people_in_space.return_value = 7
        mock_iss.current_location.return_value = {
            "latitude": "40.271698",
            "longitude": "15.619478",
        }
        mock_iss_class.return_value = mock_iss
        yield mock_iss


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pyiss: MagicMock
) -> MockConfigEntry:
    """Set up the ISS integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
