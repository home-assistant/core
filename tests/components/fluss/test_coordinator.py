"""Tests for Fluss+ DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from fluss_api import FlussApiClientError
import pytest

from homeassistant.components.fluss.coordinator import FlussDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import mock_api_client, mock_config_entry


@pytest.mark.asyncio
async def test_coordinator_init_success(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: MagicMock,
) -> None:
    """Test successful coordinator init."""
    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        coordinator = FlussDataUpdateCoordinator(hass, mock_config_entry)
        assert coordinator.api == mock_api_client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception",
    [FlussApiClientError, ValueError],
)
async def test_coordinator_init_error(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    exception: Exception,
) -> None:
    """Test coordinator init errors."""
    with (
        patch("fluss_api.FlussApiClient", side_effect=exception),
        pytest.raises(ConfigEntryNotReady),
    ):
        FlussDataUpdateCoordinator(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_coordinator_update_data_success(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: MagicMock,
) -> None:
    """Test successful data update."""
    mock_api_client.async_get_devices.return_value = {
        "devices": [{"deviceId": "1", "deviceName": "Test"}]
    }

    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        coordinator = FlussDataUpdateCoordinator(hass, mock_config_entry)
        data: dict[str, Any] = await coordinator._async_update_data()
        assert data == {"1": {"deviceId": "1", "deviceName": "Test"}}


@pytest.mark.asyncio
async def test_coordinator_update_data_empty(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: MagicMock,
) -> None:
    """Test update with empty devices."""
    mock_api_client.async_get_devices.return_value = {"devices": []}

    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        coordinator = FlussDataUpdateCoordinator(hass, mock_config_entry)
        data: dict[str, Any] = await coordinator._async_update_data()
        assert data == {}


@pytest.mark.asyncio
async def test_coordinator_update_data_invalid(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: MagicMock,
) -> None:
    """Test update with invalid device payloads."""
    mock_api_client.async_get_devices.return_value = {
        "devices": [{"invalid": "data"}, {"deviceId": "1", "deviceName": "Test"}]
    }

    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        coordinator = FlussDataUpdateCoordinator(hass, mock_config_entry)
        data: dict[str, Any] = await coordinator._async_update_data()
        assert data == {"1": {"deviceId": "1", "deviceName": "Test"}}


@pytest.mark.asyncio
async def test_coordinator_update_data_error(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: MagicMock,
) -> None:
    """Test update data error."""
    mock_api_client.async_get_devices.side_effect = FlussApiClientError("API Error")

    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        coordinator = FlussDataUpdateCoordinator(hass, mock_config_entry)
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_refresh_interval(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_api_client: MagicMock,
) -> None:
    """Test refresh interval is set."""
    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        coordinator = FlussDataUpdateCoordinator(hass, mock_config_entry)
        assert coordinator.update_interval == timedelta(minutes=5)  # Assuming UPDATE_INTERVAL_TIMEDELTA is 5 min