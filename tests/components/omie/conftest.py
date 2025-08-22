"""Common fixtures for the OMIE - Spain and Portugal electricity prices tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.omie.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def hass_lisbon(hass: HomeAssistant):
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Lisbon")
    return hass


@pytest.fixture
async def hass_madrid(hass: HomeAssistant):
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Madrid")
    return hass


@pytest.fixture
def mock_pyomie():
    """Mock pyomie.spot_price with realistic responses."""
    with patch("homeassistant.components.omie.coordinator.pyomie") as mock:
        # Mock successful responses - return different mock objects for each call
        async def mock_spot_price(session, market_date):
            mock_result = Mock()
            mock_result.market_date = market_date
            mock_result.contents = Mock()
            mock_result.updated_at = Mock()
            return mock_result

        mock.spot_price.side_effect = mock_spot_price
        yield mock
