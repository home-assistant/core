"""Tests for the Pooldose coordinator."""

import datetime
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.mark.asyncio
async def test_coordinator_fetches_data(hass: HomeAssistant) -> None:
    """Test that the coordinator fetches data from the API."""
    mock_api = AsyncMock()
    mock_api.get_instant_values.return_value = {"ph": 7.2, "orp": 650}

    coordinator = PooldoseCoordinator(
        hass,
        api=mock_api,
        update_interval=datetime.timedelta(seconds=30),
    )

    data = await coordinator._async_update_data()
    assert data == {"ph": 7.2, "orp": 650}
    mock_api.get_instant_values.assert_awaited_once()


@pytest.mark.asyncio
async def test_coordinator_handles_api_error(hass: HomeAssistant) -> None:
    """Test that the coordinator handles API errors."""
    mock_api = AsyncMock()
    mock_api.get_instant_values.side_effect = Exception("API error")

    coordinator = PooldoseCoordinator(
        hass,
        api=mock_api,
        update_interval=datetime.timedelta(seconds=30),
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
