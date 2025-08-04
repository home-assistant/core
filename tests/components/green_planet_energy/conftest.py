"""Test fixtures for Green Planet Energy integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test@example.com",
            "password": "test_password",
            "customer_number": "12345",
            "postal_code": "12345",
        },
        unique_id="green_planet_energy",
    )


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Create a mocked aiohttp session."""
    mock_session = MagicMock()

    # Mock response data in the correct format expected by the coordinator
    # Format: {"result": {"datum": [...], "wert": [...]}}

    # Create datum array with proper timestamp format
    # Today's data: "04.08.25, HH:00 Uhr"
    datum_array = [f"04.08.25, {hour:02d}:00 Uhr" for hour in range(24)]
    # Tomorrow's data: "05.08.25, HH:00 Uhr"
    datum_array.extend([f"05.08.25, {hour:02d}:00 Uhr" for hour in range(24)])

    # Create wert array (prices as strings with German decimal comma format)
    # Today's prices: 0.20 + (hour * 0.01)
    wert_array = [f"{0.20 + (hour * 0.01):.2f}".replace(".", ",") for hour in range(24)]
    # Tomorrow's prices: 0.25 + (hour * 0.01) (slightly different for testing)
    wert_array.extend(
        [f"{0.25 + (hour * 0.01):.2f}".replace(".", ",") for hour in range(24)]
    )

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "result": {"errorCode": 0, "datum": datum_array, "wert": wert_array}
        }
    )

    mock_session.post.return_value.__aenter__.return_value = mock_response

    with patch(
        "homeassistant.components.green_planet_energy.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        yield mock_session


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> MockConfigEntry:
    """Set up the Green Planet Energy integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
