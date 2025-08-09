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
    """Create a mocked Green Planet Energy API."""
    mock_api_instance = AsyncMock()

    # Mock the API response data
    # Today's prices: 0.20 + (hour * 0.01)
    today_prices = {f"gpe_price_{hour:02d}": 0.20 + (hour * 0.01) for hour in range(24)}
    # Tomorrow's prices: 0.25 + (hour * 0.01) (slightly different for testing)
    tomorrow_prices = {
        f"gpe_price_{hour:02d}_tomorrow": 0.25 + (hour * 0.01) for hour in range(24)
    }

    # Combine all prices
    all_prices = {**today_prices, **tomorrow_prices}

    mock_api_instance.get_electricity_prices.return_value = all_prices

    with patch(
        "homeassistant.components.green_planet_energy.coordinator.GreenPlanetEnergyAPI",
        return_value=mock_api_instance,
    ):
        yield mock_api_instance


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> MockConfigEntry:
    """Set up the Green Planet Energy integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
