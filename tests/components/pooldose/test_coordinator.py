"""Test the Pooldose coordinator."""

import datetime
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_coordinator_fetches_data(hass: HomeAssistant) -> None:
    """Test that the coordinator fetches data from the API."""
    mock_client = AsyncMock()
    mock_client.fetch_data.return_value = (
        "SUCCESS",
        {"ph": [7.2, "pH"], "orp": [650, "mV"]},
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    mock_client.fetch_data.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_api_error(hass: HomeAssistant) -> None:
    """Test that the coordinator handles API errors."""
    mock_client = AsyncMock()
    mock_client.fetch_data.side_effect = Exception("API error")

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
    )

    await coordinator.async_refresh()

    # Coordinator should handle the exception gracefully
    assert coordinator.last_update_success is False
