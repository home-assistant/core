"""Tests for Wibeee coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.wibeee.coordinator import WibeeeCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_coordinator_update_failed(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator update failure."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())
    # Must be an exception that the coordinator catches (TimeoutError, ClientError, etc)
    mock_wibeee_api.async_fetch_sensors_data.side_effect = TimeoutError("Fetch failed")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_no_data(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator handles no data received."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())
    mock_wibeee_api.async_fetch_sensors_data.return_value = None

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_invalid_data(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator handles invalid data format."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())
    mock_wibeee_api.async_fetch_sensors_data.return_value = "invalid"

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_push_update_invalid(
    hass: HomeAssistant, mock_wibeee_api: AsyncMock
) -> None:
    """Test coordinator handles invalid push update data."""
    coordinator = WibeeeCoordinator(hass, mock_wibeee_api, config_entry=AsyncMock())

    # Push non-dict data should be ignored
    coordinator.async_push_update("not_a_dict")  # type: ignore[arg-type]
    assert coordinator.data is None
