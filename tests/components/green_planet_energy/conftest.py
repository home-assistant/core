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
        data={},
        unique_id=DOMAIN,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Create a mocked Green Planet Energy API."""
    with patch(
        "homeassistant.components.green_planet_energy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Create a mocked Green Planet Energy API."""
    with (
        patch(
            "homeassistant.components.green_planet_energy.coordinator.GreenPlanetEnergyAPI",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.green_planet_energy.config_flow.GreenPlanetEnergyAPI",
            new=mock_api_class,
        ),
    ):
        # Use MagicMock instead of AsyncMock for sync methods
        mock_api_instance = MagicMock()

        # Mock the API response data
        # Today's prices: 0.20 + (hour * 0.01)
        today_prices = {
            f"gpe_price_{hour:02d}": 0.20 + (hour * 0.01) for hour in range(24)
        }
        # Tomorrow's prices: 0.25 + (hour * 0.01) (slightly different for testing)
        tomorrow_prices = {
            f"gpe_price_{hour:02d}_tomorrow": 0.25 + (hour * 0.01) for hour in range(24)
        }

        # Combine all prices
        all_prices = {**today_prices, **tomorrow_prices}

        # Make get_electricity_prices async since coordinator uses it
        mock_api_instance.get_electricity_prices = AsyncMock(return_value=all_prices)

        # Mock the calculation methods to return actual values (not coroutines)
        # Highest price today: 0.20 + (23 * 0.01) = 0.43 at hour 23
        mock_api_instance.get_highest_price_today.return_value = 0.43
        mock_api_instance.get_highest_price_today_with_hour.return_value = (0.43, 23)

        # Lowest price day (6-22): 0.20 + (6 * 0.01) = 0.26 at hour 6
        mock_api_instance.get_lowest_price_day.return_value = 0.26
        mock_api_instance.get_lowest_price_day_with_hour.return_value = (0.26, 6)

        # Lowest price night (22-6): 0.20 + (0 * 0.01) = 0.20 at hour 0
        mock_api_instance.get_lowest_price_night.return_value = 0.20
        mock_api_instance.get_lowest_price_night_with_hour.return_value = (0.20, 0)

        # Current price depends on the hour passed to the method
        # Mock get_current_price to return the price for the requested hour
        def get_current_price_mock(data, hour):
            """Return price for a specific hour."""
            return 0.20 + (hour * 0.01)

        mock_api_instance.get_current_price.side_effect = get_current_price_mock

        mock_api_class.return_value = mock_api_instance
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
